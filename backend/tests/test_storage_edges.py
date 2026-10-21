# SPDX-License-Identifier: Apache-2.0
"""Adversarial A08 history/provenance/concurrency fixtures; tmp_path only."""
import json

import pytest

from workshop.contracts import ExecutionKey, FeedPolicy, Observation
from workshop.ingest import Acquisition, Ingest, SourceBinding, EVENT_TYPE
from workshop.storage import Storage, RecoveryRequired
from test_storage import initial, domain, emit, start, complete, KEY


@pytest.fixture
def store(tmp_path):
    s = Storage(tmp_path / 'synthetic-edges.db', initial=initial(), retention=8)
    yield s
    s.close()


def test_A08_included_terminal_absent_from_snapshot_remains_in_history(store):
    emit(store)
    token = start(store, watermark=2)
    emit(store, seq=2, at=21, id='terminal', state='succeeded', revision=2)
    store.snapshot_page(token, 'a', [])
    store.finish_snapshot(token)
    e = store.read().reducer.executions[KEY]
    assert e.lifecycle.mapped == 'succeeded'
    assert any(o.mapped == 'succeeded' for o in e.observations)
    assert emit(store, seq=2, at=22, id='terminal', state='succeeded', revision=2).duplicates == 1
    assert store.read().reducer.executions[KEY].lifecycle.mapped == 'succeeded'


def test_A08_partial_keeps_execution_received_while_collecting_pages(store):
    emit(store)
    token = start(store, watermark=2, complete=False)
    emit(store, seq=2, at=21, id='two', native='two')
    store.snapshot_page(token, 'a', [])
    store.finish_snapshot(token)
    r = store.read().reducer
    assert ExecutionKey('fixture-runtime', 'two') in r.executions
    assert r.roles['agent'].present <= r.executions.keys()


def test_A08_partial_after_restart_does_not_reacquire_live_freshness(store):
    emit(store)
    path = store.path
    store.close()
    s = Storage(path)
    complete(s, [domain()], complete=False)
    state = s.read()
    assert state.ingests['source'].reconcile_required
    assert state.reducer.executions[KEY].acquired_at is None
    assert state.reducer.feeds['runtime'].last_acquired_at is None
    assert s.snapshot(now=20)['projection']['roles'][0]['availability'] == 'unknown'
    s.close()


@pytest.mark.parametrize('evidence_class', ['inferred', 'agent_reported', 'operator_recorded', 'source_record'])
def test_A08_weak_empty_inventory_cannot_prove_runtime_availability(tmp_path, evidence_class):
    state = initial()
    i = state.ingests['source']
    state.ingests['source'] = Ingest(state.reducer, SourceBinding(i.binding.source,
        i.binding.runtime, i.binding.role, i.binding.feed, evidence_class=evidence_class))
    s = Storage(tmp_path / 'synthetic-provenance.db', initial=state)
    with s.transaction() as current:
        for name, value in [('admission', 'enabled'), ('reachability', 'reachable'),
                            ('capacity', {'limit': 1, 'used': 0})]:
            current.reducer.observe_role('agent', name, Observation(value, value,
                'fixture', 'urn:fixture:signals', 'runtime', 10), acquired_at=10)
    complete(s, [], watermark=0)
    role = s.snapshot(now=20)['projection']['roles'][0]
    assert role['availability'] == 'unknown'
    assert role['coverage'] != 'covered'
    assert s.read().ingests['source'].reconcile_required
    s.close()


def test_A08_other_source_conflict_during_snapshot_is_not_erased(tmp_path):
    state = initial()
    state.reducer.register_role('other', scope=('chat',), inventory_approved=True)
    state.reducer.register_feed('other', FeedPolicy(5, 15, 30), group='other')
    state.ingests['other'] = Ingest(state.reducer, SourceBinding('urn:fixture:other',
        'other-runtime', 'other', 'other'))
    s = Storage(tmp_path / 'synthetic-multi-source.db', initial=state)
    emit(s)
    with s.transaction() as current:
        current.reducer.add_correlation(ExecutionKey('other-runtime', 'alias'), KEY,
                                        mapping_version='fixture')
    token = start(s)
    event = dict(specversion='1.0', source='urn:fixture:other', id='other', type=EVENT_TYPE,
                 data=domain('alias', 'failed'))
    s.cloudevents('other', json.dumps(event).encode(), context=Acquisition(21, 21, 'other-boot'),
                  source_cursor=1)
    s.snapshot_page(token, 'a', [domain()])
    s.finish_snapshot(token)
    r = s.read().reducer
    assert r.executions[KEY].discrepancies
    assert KEY in r.roles['agent'].disputed
    assert KEY in r.roles['other'].disputed
    assert r.summary('agent', now=21)['availability'] == 'unknown'
    s.close()


def test_A08_ignored_old_revision_during_snapshot_does_not_shadow_repair(store):
    emit(store, revision=3)
    token = start(store)
    emit(store, seq=2, at=21, id='obsolete', revision=2)
    store.snapshot_page(token, 'a', [domain(state='succeeded', revision=4)])
    store.finish_snapshot(token)
    assert store.read().reducer.executions[KEY].lifecycle.mapped == 'succeeded'


def test_A08_newer_live_event_shadows_older_terminal_snapshot_record(store):
    emit(store)
    token = start(store)
    emit(store, seq=2, at=21, id='later-live', revision=3)
    store.snapshot_page(token, 'a', [domain(state='succeeded', revision=2)])
    store.finish_snapshot(token)
    e = store.read().reducer.executions[KEY]
    assert e.lifecycle.mapped == 'active'
    assert e.acquired_at == 21


def test_A08_snapshot_and_cursor_share_one_SQLite_read_view(store, monkeypatch):
    reader = Storage(store.path)
    emit(store)
    before = reader.snapshot(now=10)
    original = reader._load
    def load_then_race():
        state = original()
        emit(store, seq=2, at=11, id='terminal', state='succeeded', revision=2)
        return state
    monkeypatch.setattr(reader, '_load', load_then_race)
    raced = reader.snapshot(now=10)
    assert raced == before
    assert reader.replay(raced['cursor'], now=11)[-1]['projection']['executions'][0]['lifecycle']['mapped'] == 'succeeded'
    reader.close()


def test_A08_incomplete_pages_are_discarded_on_service_restart(store):
    emit(store)
    token = start(store, pages=('a', 'b'))
    store.snapshot_page(token, 'a', [domain('two')])
    path = store.path
    store.close()
    s = Storage(path)
    with pytest.raises(RecoveryRequired):
        s.finish_snapshot(token)
    assert set(s.read().reducer.executions) == {KEY}
    s.close()


def test_A08_local_control_race_requests_retry_without_losing_audit(store):
    from test_storage import rule
    emit(store)
    with store.transaction() as state:
        state.reducer.alarms.register(rule())
        state.reducer.alarms.update('lost', True, now=11)
    token = start(store)
    with store.transaction() as state:
        state.reducer.alarms.acknowledge('1', actor='fixture', now=21)
    store.snapshot_page(token, 'a', [])
    with pytest.raises(RecoveryRequired):
        store.finish_snapshot(token)
    assert store.read().reducer.alarms.audit[-1]['action'] == 'acknowledged'


def test_A08_authoritative_absence_invalidates_live_age_without_inventing_terminal(store):
    emit(store)
    complete(store, [])
    state = store.read()
    assert KEY not in state.reducer.roles['agent'].present
    assert state.reducer.executions[KEY].lifecycle.mapped == 'active'
    assert state.reducer.executions[KEY].acquired_at is None
    assert store.snapshot(now=20)['projection']['executions'][0]['lifecycle_quality'] == 'unknown'


def test_A08_snapshot_SQL_failure_keeps_pages_and_previous_projection(store):
    import sqlite3
    emit(store)
    token = start(store)
    store.snapshot_page(token, 'a', [domain(state='succeeded', revision=2)])
    db = sqlite3.connect(store.path)
    db.execute("CREATE TRIGGER synthetic_snapshot_failure BEFORE INSERT ON revisions BEGIN SELECT RAISE(ABORT, 'fixture commit failure'); END")
    db.commit()
    before = store.snapshot(now=20)
    with pytest.raises(sqlite3.DatabaseError):
        store.finish_snapshot(token)
    assert store.snapshot(now=20) == before
    db.execute('DROP TRIGGER synthetic_snapshot_failure')
    db.commit()
    db.close()
    store.finish_snapshot(token)
    assert store.read().reducer.executions[KEY].lifecycle.mapped == 'succeeded'


def test_A08_committed_WAL_survives_abrupt_service_exit(store, tmp_path):
    import subprocess
    import sys
    from pathlib import Path
    import workshop
    emit(store)
    script = tmp_path / 'synthetic-crash.py'
    # A child process intentionally skips connection cleanup after a durable
    # commit. Only the explicitly supplied fixture DB is opened.
    script.write_text('''import os, sys
sys.path.insert(0, sys.argv[2])
from workshop.storage import Storage
from workshop.ingest import Acquisition
s = Storage(sys.argv[1])
s.cloudevents('source', sys.argv[3].encode(), context=Acquisition(21,21,'boot'), source_cursor=2)
os._exit(0)
''')
    from test_storage import wire
    result = subprocess.run([sys.executable, str(script), str(store.path),
        str(Path(workshop.__file__).parent.parent), wire(id='crash-terminal', state='succeeded',
        revision=2).decode()], capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    path = store.path
    store.close()
    s = Storage(path)
    assert s.read().reducer.executions[KEY].lifecycle.mapped == 'succeeded'
    assert s.read().ingests['source']._seen
    s.close()


def test_A08_snapshot_newer_key_still_records_cross_role_identity_conflict(tmp_path):
    state = initial()
    r = state.reducer
    r.register_role('other', scope=('chat',), inventory_approved=True)
    r.register_feed('other', FeedPolicy(5, 15, 30), group='other')
    state.ingests['other'] = Ingest(r, SourceBinding('urn:fixture:other', 'other-runtime', 'other', 'other'))
    s = Storage(tmp_path / 'synthetic-correlated-race.db', initial=state)
    def emit_other(id, seq, at, revision):
        event = dict(specversion='1.0', source='urn:fixture:other', id=id, type=EVENT_TYPE,
                     data=domain('canonical', revision=revision))
        return s.cloudevents('other', json.dumps(event).encode(),
                            context=Acquisition(at, at, 'other-boot'), source_cursor=seq)
    emit_other('initial', 1, 10, 1)
    canonical = ExecutionKey('other-runtime', 'canonical')
    with s.transaction() as current:
        current.reducer.add_correlation(KEY, canonical, mapping_version='fixture')
        for name, value in [('admission', 'enabled'), ('reachability', 'reachable'),
                            ('capacity', {'limit': 1, 'used': 0})]:
            current.reducer.observe_role('agent', name, Observation(value, value,
                'fixture', 'urn:fixture:signals', 'runtime', 10), acquired_at=10)
    token = start(s, watermark=0)
    emit_other('newer', 2, 21, 2)
    s.snapshot_page(token, 'a', [domain()])
    s.finish_snapshot(token)
    current = s.read().reducer
    assert current.summary('agent', now=21)['availability'] == 'unknown'
    assert canonical in current.roles['agent'].disputed
    assert current.executions[canonical].discrepancies
    assert current.executions[canonical].acquired_at == 21
    s.close()


def test_A08_snapshot_regressive_execution_revision_cannot_overwrite_current(store):
    emit(store, revision=3)
    token = start(store)
    store.snapshot_page(token, 'a', [domain(state='failed', revision=2)])
    before = store.snapshot(now=20)
    with pytest.raises(RecoveryRequired):
        store.finish_snapshot(token)
    assert store.snapshot(now=20) == before
