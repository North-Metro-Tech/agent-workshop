# SPDX-License-Identifier: Apache-2.0
"""Adversarial regressions within A01–A04, using synthetic fixtures only."""
import pytest

from test_truth_model import ready, execution, obs, rule, model  # noqa: F401
from workshop.contracts import ExecutionKey, Observation, FeedPolicy
from workshop.api import LocalAPI


def test_A01_identical_native_execution_ids_in_different_runtimes(model):
    a = execution(model)
    b = model.observe_execution('role-a', ExecutionKey('runtime-b', 'run-a'),
        session='session-b', parent=None, task=None,
        lifecycle=obs('running', 'active'), acquired_at=0)
    assert a != b
    assert len(model.executions) == 2


def test_A01_unversioned_or_existing_alias_mapping_rejected(model):
    a, b = execution(model), execution(model, 'run-b')
    with pytest.raises(ValueError):
        model.add_correlation(ExecutionKey('hook', '1'), a, mapping_version='')
    with pytest.raises(ValueError):
        model.add_correlation(b, a, mapping_version='fixture-v1')


def test_A01_corrobating_report_does_not_replace_runtime_authority(model):
    a = execution(model)
    reported = Observation('working', 'active', 'fixture-v1', 'agent-report',
                           'executions', 1, evidence_class='agent_reported')
    model.observe_execution('role-a', a, session='session-a', parent=None,
        task=None, lifecycle=reported, acquired_at=1)
    assert model.executions[a].lifecycle.source == 'runtime'
    assert model.summary('role-a', now=1)['availability'] == 'busy'
    assert len(model.executions[a].observations) == 2


def test_A02_unsupported_terminal_mapping_never_establishes_available(model):
    ready(model)
    model.observe_execution('role-a', ExecutionKey('runtime-a', 'unsupported'),
        session='s', parent=None, task=None,
        lifecycle=obs('unknown-native', 'succeeded', supported=False), acquired_at=0)
    assert model.summary('role-a', now=0)['availability'] == 'unknown'


@pytest.mark.parametrize('field,value', [('admission', 'enabled'),
    ('reachability', 'reachable'), ('capacity', {'limit': 2, 'used': 0})])
def test_A03_inferred_or_agent_reported_values_cannot_prove_available(model, field, value):
    ready(model)
    for evidence_class in ('agent_reported', 'inferred'):
        o = Observation(value, value, 'fixture-v1', 'runtime', field, 0,
                        evidence_class=evidence_class)
        model.observe_role('role-a', field, o, acquired_at=0)
        assert model.summary('role-a', now=0)['availability'] == 'unknown'


def test_A03_same_feed_other_role_cannot_revive_reconciliation(model):
    ready(model)
    model.register_role('role-b', scope=('board',), inventory_approved=True)
    model.reconcile('role-b', [], scope=('board',), complete=True,
                    feed='executions', acquired_at=44)
    assert model.feed_quality('executions', now=45) == 'fresh'
    assert model.summary('role-a', now=45)['reconciliation_quality'] == 'stale'


def test_A03_snapshot_is_defensive_and_interlock_has_no_setter(model):
    ready(model)
    api = LocalAPI(model)
    snapshot = api.snapshot(now=0)
    snapshot['roles'][0]['signals']['capacity']['mapped']['limit'] = 0
    assert model.summary('role-a', now=0)['availability'] == 'available'
    with pytest.raises(AttributeError):
        api.native_write_enabled = True
    assert not api.native_write_enabled
    with pytest.raises(PermissionError):
        api.request('POST', '/alarms/acknowledge', position='viewer', authorized=True)


def test_A04_real_loss_group_retains_two_feeds_and_first_out(model):
    model.register_feed('metadata', FeedPolicy(60, 180, 360), group='collector-a')
    model.enable_feed_alarm('executions', rule())
    model.enable_feed_alarm('metadata', rule('loss-b'))
    ready(model)
    model.acquire('metadata', 0)
    model.tick(now=45)
    first = model.alarms.occurrences[0]
    model.tick(now=180)
    groups = model.alarms.incidents()
    assert len(groups) == 1
    assert groups[0]['first_out'] == first.id
    assert len(groups[0]['children']) == 2
    assert all(o.condition for o in model.alarms.occurrences)


def test_A04_recurrence_before_ack_retains_original_first_out(model):
    a = model.alarms
    a.register(rule())
    first = a.update('loss-a', True, now=0)
    a.update('loss-a', False, now=1)
    second = a.update('loss-a', True, now=2)
    assert first.id != second.id
    assert first.state(now=2) == 'return-to-normal-unacked'
    assert a.incidents()[0]['first_out'] == first.id
    a.acknowledge(first.id, now=3, actor='operator')
    assert first.state(now=3) == 'normal'
    assert second.state(now=3) == 'unacknowledged'
    assert a.incidents()[0]['first_out'] == first.id


def test_A04_shelved_recurrence_auto_expiry_and_audit(model):
    a = model.alarms
    a.register(rule())
    first = a.update('loss-a', True, now=0)
    a.shelve('loss-a', until=10, actor='operator', reason='Repair', now=1)
    a.update('loss-a', False, now=2)
    a.acknowledge(first.id, now=3, actor='operator')
    second = a.update('loss-a', True, now=4)
    assert second.state(now=9) == 'shelved'
    model.tick(now=10)
    assert second.state(now=10) == 'unacknowledged'
    assert any(e['action'] == 'shelving-expired' for e in a.audit)


def test_A04_return_normal_while_shelved_is_visible_after_expiry(model):
    a = model.alarms
    a.register(rule())
    o = a.update('loss-a', True, now=0)
    a.shelve('loss-a', until=10, actor='operator', reason='Repair', now=1)
    a.update('loss-a', False, now=2)
    assert o.state(now=10) == 'return-to-normal-unacked'


def test_A04_delay_chatter_never_creates_dropped_or_invented_alarm(model):
    a = model.alarms
    a.register(rule(on_delay=5, off_delay=3))
    assert a.update('loss-a', True, now=0) is None
    assert a.update('loss-a', False, now=4) is None
    assert a.occurrences == []
    a.update('loss-a', True, now=5)
    o = a.update('loss-a', True, now=10)
    a.update('loss-a', False, now=11)
    a.update('loss-a', True, now=13)
    assert o.condition
    assert len(a.occurrences) == 1


def test_A04_simultaneous_first_out_marks_uncertainty(model):
    a = model.alarms
    a.register(rule())
    a.register(rule('loss-b'))
    a.update('loss-a', True, now=0)
    a.update('loss-b', True, now=0)
    assert a.incidents()[0]['ordering_uncertain']


@pytest.mark.parametrize('bad_time', [float('nan'), float('inf'), True])
def test_A04_invalid_clock_cannot_fabricate_freshness(model, bad_time):
    with pytest.raises(ValueError):
        model.acquire('executions', bad_time)


def test_A04_caller_mutation_cannot_change_native_observation(model):
    value = {'limit': 1, 'used': 0}
    ready(model)
    model.observe_role('role-a', 'capacity', obs(value, value, feed='capacity'), acquired_at=0)
    value['limit'] = 0
    assert model.summary('role-a', now=0)['availability'] == 'available'


def test_A01_cross_role_identity_conflict_blocks_both_roles(model):
    ready(model)
    model.register_role('role-b', scope=('chat', 'board'), inventory_approved=True)
    model.reconcile('role-b', [], scope=('chat', 'board'), complete=True,
                    feed='executions', acquired_at=0)
    for name, (o, at) in model.roles['role-a'].signals.items():
        model.observe_role('role-b', name, o, acquired_at=at)
    assert model.summary('role-b', now=0)['availability'] == 'available'
    a = execution(model)
    model.observe_execution('role-b', a, session='session-a', parent=None,
        task=None, lifecycle=obs('running', 'active'), acquired_at=1)
    assert model.summary('role-a', now=1)['availability'] == 'unknown'
    assert model.summary('role-b', now=1)['availability'] == 'unknown'


def test_A02_execution_projection_exposes_native_mapping_and_quality(model):
    model.observe_execution('role-a', ExecutionKey('runtime-a', 'unsupported'),
        session='s', parent=None, task=None,
        lifecycle=obs('future-native', None, supported=False), acquired_at=0)
    projection = LocalAPI(model).snapshot(now=45)['executions'][0]
    assert projection['lifecycle']['native'] == 'future-native'
    assert projection['lifecycle']['mapping_version'] == 'fixture-v1'
    assert projection['lifecycle_quality'] == 'unsupported'
    assert projection['acquisition_age'] == 45


def test_A03_unverified_terminal_report_cannot_prove_available(model):
    ready(model)
    o = Observation('done', 'succeeded', 'fixture-v1', 'report', 'executions',
                    0, evidence_class='agent_reported')
    model.observe_execution('role-a', ExecutionKey('runtime-a', 'report'),
        session='s', parent=None, task=None, lifecycle=o, acquired_at=0)
    assert model.summary('role-a', now=0)['availability'] == 'unknown'


def test_A04_delay_preserves_original_ordering_uncertainty(model):
    a = model.alarms
    a.register(rule(on_delay=5))
    a.update('loss-a', True, now=0, reliable_order=False)
    a.update('loss-a', True, now=5, reliable_order=True)
    assert a.incidents()[0]['ordering_uncertain']


def test_A04_manual_unshelve_reevaluates_without_clearing_condition(model):
    a = model.alarms
    a.register(rule())
    o = a.update('loss-a', True, now=0)
    a.shelve('loss-a', until=10, actor='operator', reason='Repair', now=1)
    a.unshelve('loss-a', actor='operator', reason='Resume annunciation', now=2)
    assert o.state(now=2) == 'unacknowledged'
    assert o.condition and not o.acknowledged
