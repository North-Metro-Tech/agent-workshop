# SPDX-License-Identifier: Apache-2.0
"""Synthetic A01–A04 acceptance fixtures; no runtime/database access."""
import pytest

from workshop.contracts import ExecutionKey, TaskKey, Observation, FeedPolicy, AlarmRule
from workshop.reducer import Reducer
from workshop.api import LocalAPI


@pytest.fixture
def model():
    r = Reducer()
    r.register_role('role-a', scope=('chat', 'board'), inventory_approved=True)
    for name in ('executions', 'admission', 'reachability', 'capacity', 'transport'):
        r.register_feed(name, FeedPolicy(15, 45, 120), group='collector-a')
    return r


def obs(native, mapped=None, *, feed='executions', source='runtime', supported=True):
    return Observation(native, mapped, 'fixture-v1', source, feed, 0, supported)


def ready(r, *, at=0, complete=True, scope=('chat', 'board')):
    r.reconcile('role-a', [], scope=scope, complete=complete, feed='executions', acquired_at=at)
    r.observe_role('role-a', 'admission', obs('open', 'enabled', feed='admission'), acquired_at=at)
    r.observe_role('role-a', 'reachability', obs('reachable', 'reachable', feed='reachability'), acquired_at=at)
    r.observe_role('role-a', 'capacity', obs({'limit': 2, 'used': 0}, {'limit': 2, 'used': 0}, feed='capacity'), acquired_at=at)


def execution(r, native='run-a', *, session='session-a', parent=None, task=None, source='runtime', canonical=None):
    return r.observe_execution('role-a', ExecutionKey('runtime-a', native), session=session,
        parent=parent, task=task, lifecycle=obs('running', 'active', source=source),
        acquired_at=0, canonical=canonical)


def rule(name='loss-a', group='collector-a', **kw):
    return AlarmRule(name=name, group=group, cause='Observation path lost',
        consequence='Current state cannot be established', action='Check collector',
        response_time='Before relying on state', scope='fixture', priority='attention',
        owner='fixture-owner', **kw)


def test_A01_concurrent_executions_preserve_identity(model):
    parent = ExecutionKey('runtime-a', 'parent')
    ta = TaskKey('tasks-a', 'board-a', '1')
    tb = TaskKey('tasks-a', 'board-b', '1')
    a = execution(model, parent=parent, task=ta)
    b = execution(model, 'run-b', session='session-b', task=tb)
    assert a != b
    assert len(model.executions) == 2
    assert model.executions[a].session == 'session-a'
    assert model.executions[b].session == 'session-b'
    assert model.executions[a].parent == parent
    assert model.executions[a].task != model.executions[b].task


def test_A01_explicit_multisource_mapping_deduplicates(model):
    a = execution(model)
    model.add_correlation(ExecutionKey('hook-runtime', 'hook-run'), a, mapping_version='fixture-v1')
    b = model.observe_execution('role-a', ExecutionKey('hook-runtime', 'hook-run'),
        session='session-a', parent=None, task=None,
        lifecycle=obs('started', 'active', source='hook'), acquired_at=1)
    assert a == b
    assert len(model.executions) == 1
    assert {o.source for o in model.executions[a].observations} == {'runtime', 'hook'}


def test_A01_similarity_never_merges_and_ambiguity_visible(model):
    a = execution(model)
    b = execution(model, 'run-b', session='session-a')
    model.note_ambiguity((a, b), reason='No explicit native correlation')
    assert len(model.executions) == 2
    assert model.ambiguities[0].candidates == (a, b)
    assert model.ambiguities[0].reason


def test_A01_conflicting_explicit_identity_is_not_silently_overwritten(model):
    a = execution(model)
    model.observe_execution('role-a', a, session='different-session', parent=None,
        task=None, lifecycle=obs('running', 'active', source='hook'), acquired_at=1)
    assert model.executions[a].session == 'session-a'
    assert model.executions[a].discrepancies
    assert model.summary('role-a', now=1)['availability'] != 'available'


def test_A02_configured_unobserved_never_available(model):
    s = model.summary('role-a', now=0)
    assert s['availability'] == 'unknown'
    assert s['coverage'] == 'not_configured'
    assert s['active_executions'] == []


@pytest.mark.parametrize('complete,scope', [(False, ('chat', 'board')), (True, ('board',))])
def test_A02_partial_scope_explicit(model, complete, scope):
    ready(model, complete=complete, scope=scope)
    s = model.summary('role-a', now=0)
    assert s['availability'] == 'unknown'
    assert s['coverage'] == 'partial'
    assert s['claimed_scope'] == scope


@pytest.mark.parametrize('native,mapped,supported,quality', [
    ('new-native-value', None, True, 'unknown'),
    ('open', None, False, 'unsupported'),
])
def test_A02_unknown_and_unsupported_values_preserved(model, native, mapped, supported, quality):
    ready(model)
    value = obs(native, mapped, feed='admission', supported=supported)
    model.observe_role('role-a', 'admission', value, acquired_at=1)
    s = model.summary('role-a', now=1)
    assert s['availability'] == 'unknown'
    assert s['signals']['admission']['native'] == native
    assert s['signals']['admission']['quality'] == quality
    assert s['signals']['admission']['mapping_version'] == 'fixture-v1'
    assert s['signals']['admission']['source'] == 'runtime'


def test_A02_inventory_incomplete_prevents_global_availability(model):
    model.register_role('unapproved', scope=('board',), inventory_approved=False)
    ready(model)
    model.reconcile('unapproved', [], scope=('board',), complete=True,
        feed='executions', acquired_at=0)
    assert model.summary('unapproved', now=0)['inventory'] == 'incomplete'
    assert model.summary('unapproved', now=0)['availability'] == 'unknown'


def test_A03_available_only_with_all_fresh_evidence_idle_never_alarms(model):
    ready(model)
    assert model.summary('role-a', now=1)['availability'] == 'available'
    assert model.summary('role-a', now=1)['coverage'] == 'covered'
    assert model.alarms.occurrences == []


@pytest.mark.parametrize('field,mapped', [('admission', 'held'), ('reachability', 'unknown'),
    ('capacity', {'limit': 0, 'used': 0}), ('capacity', {'limit': 2, 'used': 2}),
    ('capacity', {'limit': 2, 'used': -1}), ('capacity', {'limit': 2})])
def test_A03_unsafe_evidence_never_available(model, field, mapped):
    ready(model)
    model.observe_role('role-a', field, obs(mapped, mapped, feed=field), acquired_at=1)
    assert model.summary('role-a', now=1)['availability'] == 'unknown'


@pytest.mark.parametrize('missing', ['admission', 'reachability', 'capacity'])
def test_A03_missing_signal_never_available(model, missing):
    model.reconcile('role-a', [], scope=('chat', 'board'), complete=True,
        feed='executions', acquired_at=0)
    for field, value in [('admission', 'enabled'), ('reachability', 'reachable'),
                         ('capacity', {'limit': 1, 'used': 0})]:
        if field != missing:
            model.observe_role('role-a', field, obs(value, value, feed=field), acquired_at=0)
    assert model.summary('role-a', now=0)['availability'] == 'unknown'


def test_A03_active_execution_prevents_available_and_preserves_concurrency(model):
    ready(model)
    a, b = execution(model), execution(model, 'run-b')
    s = model.summary('role-a', now=1)
    assert s['availability'] == 'busy'
    assert s['active_executions'] == [a, b]
    assert model.summary('role-a', now=45)['availability'] == 'unknown'


def test_A03_unknown_execution_cannot_mean_zero_active(model):
    ready(model)
    model.observe_execution('role-a', ExecutionKey('runtime-a', 'mystery'), session='s',
        parent=None, task=None, lifecycle=obs('novel'), acquired_at=0)
    assert model.summary('role-a', now=1)['availability'] == 'unknown'


@pytest.mark.parametrize('path', ['/runtime/dispatch', '/runtime/cancel', '/runtime/steer',
    '/runtime/approve', '/runtime/admission', '/runtime/execute'])
def test_A03_no_effective_native_write_path(model, path):
    api = LocalAPI(model)
    assert api.snapshot(now=0)['native_write_enabled'] is False
    for position in ('viewer', 'operator', 'controller'):
        with pytest.raises(LookupError):
            api.request('POST', path, position=position, authorized=True)


def test_A03_ack_is_local_authorized_only(model):
    execution(model, task=TaskKey('task-source', 'board', '1'))
    model.alarms.register(rule())
    occurrence = model.alarms.update('loss-a', True, now=0)
    api = LocalAPI(model)
    with pytest.raises(PermissionError):
        api.acknowledge(occurrence.id, now=1, authorized=False)
    before = dict(model.executions)
    api.acknowledge(occurrence.id, now=1, authorized=True)
    assert model.executions == before
    assert occurrence.condition is True
    assert occurrence.state(now=1) == 'acknowledged'


@pytest.mark.parametrize('now,expected', [(44, 'fresh'), (45, 'stale'), (119, 'stale'), (120, 'disconnected')])
def test_A04_per_feed_deadlines_unrelated_traffic_cannot_refresh(model, now, expected):
    ready(model)
    model.acquire('transport', now)
    assert model.feed_quality('executions', now=now) == expected
    assert model.feed_quality('transport', now=now) == 'fresh'
    if now >= 45:
        assert model.summary('role-a', now=now)['availability'] == 'unknown'
        assert model.summary('role-a', now=now)['coverage'] == 'unreachable' if now >= 120 else model.summary('role-a', now=now)['coverage'] == 'partial'


def test_A04_feed_freshness_cannot_refresh_individual_signal_or_reconciliation(model):
    ready(model)
    model.acquire('executions', 44)
    model.acquire('admission', 44)
    assert model.summary('role-a', now=45)['availability'] == 'unknown'
    assert model.summary('role-a', now=45)['signals']['admission']['quality'] == 'stale'


def test_A04_metadata_feed_has_its_own_policy(model):
    model.register_feed('metadata', FeedPolicy(60, 180, 360), group='metadata')
    model.acquire('metadata', 0)
    assert model.feed_quality('metadata', now=60) == 'fresh'
    assert model.feed_quality('metadata', now=180) == 'stale'
    with pytest.raises(ValueError):
        FeedPolicy(60, 45, 120)


def test_A04_freshness_loss_not_offline_and_not_out_of_service(model):
    ready(model)
    model.enable_feed_alarm('executions', rule())
    model.tick(now=120)
    s = model.summary('role-a', now=120)
    assert s['indication'] == 'telemetry lost'
    assert model.alarms.occurrences[0].state(now=120) == 'unacknowledged'


def test_A04_alarm_ack_clear_and_clear_before_ack(model):
    alarms = model.alarms
    alarms.register(rule())
    a = alarms.update('loss-a', True, now=0)
    assert a.state(now=0) == 'unacknowledged'
    alarms.acknowledge(a.id, now=1, actor='local-operator')
    assert a.state(now=1) == 'acknowledged'
    assert a.condition is True
    alarms.update('loss-a', False, now=2)
    assert a.state(now=2) == 'normal'
    b = alarms.update('loss-a', True, now=3)
    assert b.id != a.id
    alarms.update('loss-a', False, now=4)
    assert b.state(now=4) == 'return-to-normal-unacked'
    assert alarms.incidents()[0]['first_out'] == b.id
    alarms.acknowledge(b.id, now=5, actor='local-operator')
    assert b.state(now=5) == 'normal'
    assert alarms.audit


def test_A04_grouping_preserves_children_first_out_and_uncertainty(model):
    a = model.alarms
    a.register(rule())
    a.register(rule('loss-b'))
    a.register(rule('other', group='collector-b'))
    first = a.update('loss-b', True, now=1)
    second = a.update('loss-a', True, now=2)
    a.update('other', True, now=3)
    a.update('loss-b', False, now=4)
    groups = {g['group']: g for g in a.incidents()}
    assert len(groups) == 2
    assert groups['collector-a']['first_out'] == first.id
    assert groups['collector-a']['children'] == [first.id, second.id]
    assert groups['collector-a']['ordering_uncertain'] is False
    a.register(rule('loss-c'))
    a.update('loss-c', True, now=2, reliable_order=False)
    assert a.incidents()[0]['ordering_uncertain'] is True


def test_A04_suppression_shelving_and_maintenance_preserve_underlying_condition(model):
    a = model.alarms
    a.register(rule())
    o = a.update('loss-a', True, now=0)
    a.suppress('loss-a', True, reason='Configured upstream outage', now=1)
    assert o.state(now=1) == 'suppressed-by-design'
    assert o.condition and not o.acknowledged
    a.suppress('loss-a', False, reason='Upstream restored', now=2)
    assert o.state(now=2) == 'unacknowledged'
    a.shelve('loss-a', until=10, reason='Repair in progress', actor='operator', now=3)
    assert o.state(now=9) == 'shelved'
    assert o.state(now=10) == 'unacknowledged'
    a.out_of_service('loss-a', True, owner='maintainer', reason='Inspection', now=11)
    assert o.state(now=11) == 'out-of-service'
    a.out_of_service('loss-a', False, owner='maintainer', reason='Complete', now=12)
    assert o.state(now=12) == 'unacknowledged'
    assert len(a.occurrences) == 1
    assert len(a.audit) >= 5


def test_A04_suppression_does_not_erase_clear_before_ack(model):
    a = model.alarms
    a.register(rule())
    o = a.update('loss-a', True, now=0)
    a.suppress('loss-a', True, reason='Configured', now=1)
    a.update('loss-a', False, now=2)
    assert o.state(now=2) == 'suppressed-by-design'
    a.suppress('loss-a', False, reason='Removed', now=3)
    assert o.state(now=3) == 'return-to-normal-unacked'


def test_A04_on_off_delays_do_not_hide_signal_quality(model):
    model.enable_feed_alarm('executions', rule(on_delay=5, off_delay=3))
    ready(model)
    model.tick(now=45)
    assert model.feed_quality('executions', now=45) == 'stale'
    assert model.alarms.occurrences == []
    model.tick(now=50)
    o = model.alarms.occurrences[0]
    ready(model, at=51)
    model.tick(now=51)
    assert o.condition
    model.tick(now=54)
    assert o.state(now=54) == 'return-to-normal-unacked'


def test_A04_unrationalised_alarm_and_unaudited_suppression_rejected(model):
    with pytest.raises(ValueError):
        AlarmRule(name='bad', group='g', cause='', consequence='', action='',
                  response_time='', scope='', priority='', owner='')
    model.alarms.register(rule())
    with pytest.raises(ValueError):
        model.alarms.suppress('loss-a', True, reason='', now=0)
    with pytest.raises(ValueError):
        model.alarms.shelve('loss-a', until=1, reason='x', actor='', now=0)
