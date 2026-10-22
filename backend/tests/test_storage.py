# SPDX-License-Identifier: Apache-2.0
"""Synthetic A08 fixtures. Every database is owned by pytest tmp_path."""
from copy import deepcopy
import json
import sqlite3

import pytest

from workshop.api import LocalAPI
from workshop.contracts import AlarmRule, ExecutionKey, FeedPolicy, Observation, TaskKey
from workshop.ingest import Acquisition, EVENT_TYPE, Ingest, SourceBinding
from workshop.reducer import Reducer
from workshop.storage import RecoveryRequired, State, Storage


KEY = ExecutionKey('fixture-runtime', 'one')


def initial():
    r = Reducer()
    r.register_role('agent', scope=('chat', 'cron'), inventory_approved=True)
    r.register_feed('runtime', FeedPolicy(5, 15, 30), group='fixture')
    i = Ingest(r, SourceBinding('urn:fixture:source', 'fixture-runtime', 'agent', 'runtime'))
    return State(r, {'source': i})


def domain(native='one', state='active', revision=1):
    return dict(execution_id=native, session_id='session', lifecycle=state, revision=revision)


def wire(id='event', native='one', state='active', revision=1, **extensions):
    return json.dumps(dict(specversion='1.0', source='urn:fixture:source', id=id,
                           type=EVENT_TYPE, data=domain(native, state, revision), **extensions)).encode()


def emit(s, seq=1, at=10, epoch='boot', **kw):
    return s.cloudevents('source', wire(**kw), context=Acquisition(at, at, epoch), source_cursor=seq)


@pytest.fixture
def store(tmp_path):
    s = Storage(tmp_path / 'synthetic.db', initial=initial(), retention=8)
    yield s
    s.close()


def start(s, *, generation=1, watermark=1, pages=('a',), complete=True,
          scope=('chat', 'cron'), at=20, epoch='boot'):
    return s.begin_snapshot('source', generation=generation, watermark=watermark,
                            pages=pages, complete=complete, scope=scope,
                            acquired_at=at, epoch=epoch)


def complete(s, records=(), **kw):
    token = start(s, **kw)
    s.snapshot_page(token, 'a', list(records))
    return s.finish_snapshot(token)


def rule(name='lost', **kw):
    return AlarmRule(name, 'fixture', 'missing feed', 'unknown visibility', 'inspect source',
                     'soon', 'fixture scope', 'high', 'operator', **kw)


def test_A08_migration_WAL_and_domain_tables(store):
    db = sqlite3.connect(store.path)
    assert db.execute('PRAGMA journal_mode').fetchone()[0] == 'wal'
    assert db.execute('PRAGMA user_version').fetchone()[0] == 2
    tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {'executions', 'roles', 'feeds', 'correlations', 'ambiguities', 'alarm_occurrences',
            'alarm_audit', 'alarm_rules', 'alarm_controls', 'ingests', 'revisions'} <= tables
    db.close()


def test_A08_missing_terminal_repaired_by_snapshot_without_event(store):
    emit(store)
    complete(store, [domain(state='succeeded', revision=2)])
    state = store.read()
    assert state.reducer.executions[KEY].lifecycle.mapped == 'succeeded'
    assert state.reducer.roles['agent'].complete
    assert not state.ingests['source'].reconcile_required
    assert state.reducer.executions[KEY].acquired_at == 20


def test_A08_restart_keeps_history_but_invalidates_live_evidence(store):
    emit(store)
    with store.transaction() as state:
        r = state.reducer
        for name, value in [('admission', 'enabled'), ('reachability', 'reachable'),
                            ('capacity', {'limit': 1, 'used': 0})]:
            r.observe_role('agent', name, Observation(value, value, 'fixture-v1',
                'urn:fixture:source', 'runtime', 10), acquired_at=10)
    complete(store, [domain()])
    path = store.path
    store.close()
    reopened = Storage(path)
    state = reopened.read()
    assert state.reducer.executions[KEY].lifecycle.mapped == 'active'
    assert state.reducer.executions[KEY].acquired_at is None
    assert state.reducer.feeds['runtime'].last_acquired_at is None
    assert not state.reducer.roles['agent'].complete
    assert all(at is None for _, at in state.reducer.roles['agent'].signals.values())
    assert state.ingests['source'].reconcile_required
    assert reopened.snapshot(now=20)['projection']['roles'][0]['availability'] == 'unknown'
    complete(reopened, [domain(state='succeeded', revision=2)], generation=2, at=21)
    assert reopened.read().reducer.roles['agent'].complete
    reopened.close()


def test_A08_restart_preserves_terminal_identity_order_and_redaction(store):
    emit(store, state='succeeded', revision=3, secretextension='PRIVATE_PAYLOAD')
    path = store.path
    store.close()
    s = Storage(path)
    assert emit(s, seq=1, at=20, state='succeeded', revision=3,
                secretextension='PRIVATE_PAYLOAD').duplicates == 1
    with pytest.raises(ValueError, match='identity'):
        emit(s, seq=2, at=21, state='failed', revision=4)
    emit(s, seq=2, at=22, id='older', revision=2)
    state = s.read()
    assert state.reducer.executions[KEY].lifecycle.mapped == 'succeeded'
    assert len(state.reducer.executions[KEY].observations) == 1
    assert 'PRIVATE_PAYLOAD' not in json.dumps(s.snapshot(now=22))
    s.close()
    assert b'PRIVATE_PAYLOAD' not in path.read_bytes()


@pytest.mark.parametrize('partial', ['incomplete', 'scope', 'unsupported'])
def test_A08_partial_snapshots_never_delete_unseen_executions(store, partial):
    emit(store)
    emit(store, seq=2, at=11, id='two', native='two')
    kw = {'complete': False} if partial == 'incomplete' else (
        {'scope': ('chat',)} if partial == 'scope' else {})
    records = [domain('two', 'novel' if partial == 'unsupported' else 'active')]
    complete(store, records, watermark=2, **kw)
    r = store.read().reducer
    assert KEY in r.roles['agent'].present
    assert len(r.executions) == 2
    assert not r.roles['agent'].complete
    assert store.read().ingests['source'].reconcile_required


def test_A08_paginated_replacement_is_atomic(store):
    emit(store)
    token = start(store, pages=('a', 'b'))
    store.snapshot_page(token, 'a', [domain('two')])
    assert set(store.read().reducer.executions) == {KEY}
    with pytest.raises(RecoveryRequired):
        store.finish_snapshot(token)
    assert KEY in store.read().reducer.roles['agent'].present
    store.snapshot_page(token, 'b', [domain('three')])
    store.finish_snapshot(token)
    r = store.read().reducer
    assert r.roles['agent'].present == {ExecutionKey('fixture-runtime', x) for x in ('two', 'three')}
    assert KEY in r.executions  # retained history, never fabricated terminal
    assert r.executions[KEY].lifecycle.mapped == 'active'


def test_A08_snapshot_event_race_replays_only_above_source_watermark(store):
    emit(store)
    token = start(store, watermark=2)
    emit(store, seq=2, at=21, id='included', state='active', revision=2)
    emit(store, seq=3, at=22, id='newer', native='two', revision=3)
    store.snapshot_page(token, 'a', [domain(state='succeeded', revision=3)])
    store.finish_snapshot(token)
    r = store.read().reducer
    assert r.executions[KEY].lifecycle.mapped == 'succeeded'
    assert r.executions[ExecutionKey('fixture-runtime', 'two')].acquired_at == 22
    assert len(r.roles['agent'].present) == 2
    assert store.read().source_cursors['source'] == 3


def test_A08_snapshot_old_active_cannot_overwrite_new_terminal(store):
    emit(store)
    token = start(store)
    emit(store, seq=2, at=22, id='terminal', state='succeeded', revision=2)
    store.snapshot_page(token, 'a', [domain()])
    store.finish_snapshot(token)
    assert store.read().reducer.executions[KEY].lifecycle.mapped == 'succeeded'
    assert store.read().reducer.executions[KEY].acquired_at == 22


def test_A08_epoch_change_during_snapshot_forces_reconciliation(store):
    emit(store)
    token = start(store)
    emit(store, seq=2, at=21, epoch='boot-2', id='new-epoch')
    store.snapshot_page(token, 'a', [domain(state='succeeded', revision=2)])
    with pytest.raises(RecoveryRequired):
        store.finish_snapshot(token)
    assert store.read().ingests['source'].reconcile_required
    assert store.read().reducer.executions[KEY].lifecycle.mapped == 'active'
    complete(store, [domain(state='succeeded', revision=2)], epoch='boot-2', generation=2,
             watermark=2, at=23)
    assert not store.read().ingests['source'].reconcile_required


@pytest.mark.parametrize('fault', ['page', 'duplicate-body', 'duplicate-key', 'generation',
                                  'watermark', 'scope', 'clock', 'manifest'])
def test_A08_invalid_snapshot_cannot_mutate_domain(store, fault):
    emit(store)
    before = store.snapshot(now=20)
    if fault in {'generation', 'watermark', 'scope', 'clock', 'manifest'}:
        opts = {'generation': 0} if fault == 'generation' else (
            {'watermark': 0} if fault == 'watermark' else (
            {'scope': ('alien',)} if fault == 'scope' else (
            {'at': float('nan')} if fault == 'clock' else {'pages': ('a', 'a')})))
        with pytest.raises(ValueError):
            start(store, **opts)
    else:
        token = start(store)
        if fault == 'page':
            with pytest.raises(ValueError):
                store.snapshot_page(token, 'alien', [])
        elif fault == 'duplicate-body':
            store.snapshot_page(token, 'a', [domain()])
            with pytest.raises(ValueError):
                store.snapshot_page(token, 'a', [domain(state='failed')])
        else:
            with pytest.raises(ValueError):
                store.snapshot_page(token, 'a', [domain(), domain()])
    assert store.snapshot(now=20) == before


def test_A08_old_generation_and_stale_tokens_rejected(store):
    emit(store)
    old = start(store)
    new = start(store, generation=2)
    with pytest.raises(RecoveryRequired):
        store.snapshot_page(old, 'a', [])
    store.snapshot_page(new, 'a', [])
    store.finish_snapshot(new)
    with pytest.raises(ValueError):
        start(store, generation=2)


def test_A08_browser_reconnect_and_expired_cursor(store):
    snap = store.snapshot(now=10)
    emit(store)
    entries = store.replay(snap['cursor'], now=10)
    assert len(entries) == 1
    assert entries[-1]['projection'] == store.snapshot(now=10)['projection']
    assert store.replay(entries[-1]['cursor'], now=10) == []
    old = snap['cursor']
    for n in range(2, 13):
        emit(store, seq=n, at=10+n, id=f'event-{n}', revision=n)
    with pytest.raises(RecoveryRequired):
        store.replay(old, now=23)
    fresh = store.snapshot(now=23)
    assert store.replay(fresh['cursor'], now=23) == []
    assert not fresh['projection']['native_write_enabled']


@pytest.mark.parametrize('cursor', ['', 'bad', 'other:1', 'false:-1', 'false:999999'])
def test_A08_foreign_or_invalid_browser_cursor_forces_snapshot(store, cursor):
    with pytest.raises(RecoveryRequired):
        store.replay(cursor, now=10)


def test_A08_retention_gap_during_snapshot_preserves_live_domain(store):
    emit(store)
    token = start(store)
    for n in range(2, 13):
        emit(store, seq=n, at=20+n, id=f'event-{n}', revision=n)
    store.snapshot_page(token, 'a', [])
    before = store.snapshot(now=33)
    with pytest.raises(RecoveryRequired):
        store.finish_snapshot(token)
    assert store.snapshot(now=33) == before
    assert KEY in store.read().reducer.roles['agent'].present


def test_A08_transaction_error_rolls_back_memory_database_and_cursor(store):
    emit(store)
    before = store.snapshot(now=10)
    with pytest.raises(RuntimeError):
        with store.transaction() as state:
            state.reducer.executions.clear()
            raise RuntimeError('synthetic failure')
    assert store.snapshot(now=10) == before
    with pytest.raises(ValueError):
        with store.transaction() as state:
            state.reducer.roles['agent'].signals['bad'] = object()
    assert store.snapshot(now=10) == before


def test_A08_sql_failure_rolls_back_domain_and_revision(store):
    emit(store)
    db = sqlite3.connect(store.path)
    db.execute("CREATE TRIGGER synthetic_failure BEFORE INSERT ON executions BEGIN SELECT RAISE(ABORT, 'fixture disk failure'); END")
    db.commit()
    before = store.snapshot(now=10)
    with pytest.raises(sqlite3.DatabaseError):
        emit(store, seq=2, at=11, id='two', state='succeeded', revision=2)
    assert store.snapshot(now=10) == before
    db.execute('DROP TRIGGER synthetic_failure')
    db.commit()
    db.close()
    assert emit(store, seq=2, at=11, id='two', state='succeeded', revision=2).accepted == 1


def test_A08_alarm_audit_controls_pending_and_first_out_survive_restart(store):
    with store.transaction() as state:
        a = state.reducer.alarms
        a.register(rule())
        a.register(rule('child', on_delay=5))
        root = a.update('lost', True, now=10)
        a.acknowledge(root.id, actor='fixture-operator', now=11)
        a.shelve('lost', until=30, reason='fixture', actor='fixture-operator', now=12)
        a.update('child', True, now=13)
        a.update('lost', False, now=14)
    saved = deepcopy(store.read().reducer.alarms.audit)
    path = store.path
    store.close()
    s = Storage(path)
    with s.transaction() as state:
        a = state.reducer.alarms
        assert a.audit == saved
        assert a.occurrences[0].acknowledged_by == 'fixture-operator'
        assert a.occurrences[0].controls is a.controls['lost']
        assert a._current['lost'] is a.occurrences[0]
        child = a.update('child', True, now=18)
        assert child.raised_at == 18
        assert child.id == '2'
        a.expire_shelves(now=30)
        assert a.occurrences[0].controls.shelved_until is None
    s.close()


def test_A08_local_alarm_acknowledgement_is_durable(store):
    with store.transaction() as state:
        state.reducer.alarms.register(rule())
        state.reducer.alarms.update('lost', True, now=10)
    api = LocalAPI(storage=store)
    with pytest.raises(PermissionError):
        api.acknowledge('1', now=11)
    api.acknowledge('1', now=11, authorized=True)
    path = store.path
    store.close()
    s = Storage(path)
    a = s.read().reducer.alarms
    assert a.occurrences[0].acknowledged
    assert a.audit[-1]['action'] == 'acknowledged'
    assert a.occurrences[0].condition  # acknowledgement is not source clear
    s.close()


def test_A08_correlations_ambiguities_tasks_and_conflicts_roundtrip(store):
    emit(store)
    emit(store, seq=2, at=11, id='two', native='two')
    with store.transaction() as state:
        r = state.reducer
        r.executions[KEY].task = TaskKey('fixture-board', 'namespace', 'task')
        r.add_correlation(ExecutionKey('alias', 'one'), KEY, mapping_version='fixture-v1')
        r.note_ambiguity((KEY, ExecutionKey('fixture-runtime', 'two')), reason='fixture')
        r.executions[KEY].discrepancies.append({'source_key': KEY, 'observation':
            r.executions[KEY].lifecycle, 'parent': None})
    path = store.path
    store.close()
    s = Storage(path)
    r = s.read().reducer
    assert r.executions[KEY].task == TaskKey('fixture-board', 'namespace', 'task')
    assert r.correlations[ExecutionKey('alias', 'one')] == (KEY, 'fixture-v1')
    assert r.ambiguities[0].candidates[0] == KEY
    assert r.executions[KEY].discrepancies[0]['observation'] == r.executions[KEY].lifecycle
    assert s.read().ingests['source'].reducer is not r  # detached read values
    s.close()


def test_A08_read_returns_detached_state(store):
    emit(store)
    detached = store.read()
    assert detached.ingests['source'].reducer is detached.reducer
    detached.reducer.executions.clear()
    assert KEY in store.read().reducer.executions


def test_A08_foreign_database_is_rejected_without_modification(tmp_path):
    path = tmp_path / 'synthetic-native.db'
    db = sqlite3.connect(path)
    db.execute('CREATE TABLE native_records(id INTEGER)')
    db.execute('INSERT INTO native_records VALUES (7)')
    db.commit()
    db.close()
    before = path.read_bytes()
    with pytest.raises(ValueError):
        Storage(path, initial=initial())
    assert path.read_bytes() == before
