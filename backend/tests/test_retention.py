# SPDX-License-Identifier: Apache-2.0
"""Synthetic, assertion-bounded acquisition/recovery; no wall-clock thresholds."""
from collections import deque
from copy import deepcopy
import json
from pathlib import Path
import random
import sqlite3

import pytest

from workshop.api import LocalAPI
from workshop.contracts import ExecutionKey, Observation
from workshop.delta import difference, apply_difference
from workshop.ingest import Acquisition
from workshop.retention import (OBSERVATION_LIMIT, RECORD_LIMIT, SEEN_LIMIT,
                                RetentionCapacityError)
from workshop.storage import (Storage, RecoveryRequired, ANCHOR_INTERVAL,
                              State, _sections, _pack, _unpack, _invalidate)
from test_storage import initial, wire, emit, KEY, domain, rule
from test_hermes_work import native


def batch(s, number):
    events = [json.loads(wire(id=f'{number}-{native}', native=native,
                             state=lifecycle, revision=number))
              for native, lifecycle in [('one', 'active'), ('two', 'succeeded'), ('three', 'failed')]]
    return s.cloudevents('source', json.dumps(events).encode(),
                        context=Acquisition(number, number, 'boot'), source_cursor=number)


def measure(s):
    s._db.execute('PRAGMA wal_checkpoint(PASSIVE)')
    state = s.read()
    rows = s._db.execute('SELECT state,event FROM revisions').fetchall()
    anchors = sum(_unpack(value)['format'] == 'anchor-v2' for value, _ in rows)
    return dict(state_bytes=len(_pack(_sections(state)).encode()),
                revision_bytes=sum(len(value.encode()) + len(event.encode()) for value, event in rows),
                allocated_bytes=sum(path.stat().st_blocks * 512 for path in
                                    [s.path, Path(str(s.path)+'-wal'), Path(str(s.path)+'-shm')]
                                    if path.exists()),
                revisions=len(rows), anchors=anchors,
                observations=len(state.reducer.executions[KEY].observations),
                records=len(state.ingests['source'].records), seen=len(state.ingests['source']._seen))


def test_sustained_default_policy_bytes_restart_replay_and_protected_facts(tmp_path):
    s = Storage(tmp_path / 'bounded.db', initial=initial())
    expected = deque(maxlen=128)
    oldest_cursor = s.snapshot(now=10000)['cursor']
    samples = []
    for number in range(1, 361):
        assert batch(s, number).accepted == 3
        expected.append(s.snapshot(now=10000))
        if number in {180, 270, 360}:
            sample = measure(s)
            samples.append(sample)
            print('bounded-growth', number, json.dumps(sample, sort_keys=True))
            assert sample['state_bytes'] < 512 * 1024
            assert sample['revision_bytes'] < 8 * 1024 * 1024
            assert sample['allocated_bytes'] < 32 * 1024 * 1024
            assert sample['revisions'] == 128
            assert sample['anchors'] <= 128 // ANCHOR_INTERVAL + 1
            assert sample['observations'] == OBSERVATION_LIMIT
            assert sample['records'] == RECORD_LIMIT
            assert sample['seen'] == SEEN_LIMIT
    assert max(v['state_bytes'] for v in samples) - min(v['state_bytes'] for v in samples) < 4096
    assert max(v['allocated_bytes'] for v in samples) - min(v['allocated_bytes'] for v in samples) < 2 * 1024 * 1024
    state = s.read()
    active = state.reducer.executions[KEY]
    assert active.observation_ids == [0] + list(range(297, 360))
    assert len(s.retained_diagnostics()['records']) <= 100
    for native, mapped in [('two', 'succeeded'), ('three', 'failed')]:
        terminal = state.reducer.executions[ExecutionKey('fixture-runtime', native)]
        assert terminal.lifecycle.mapped == mapped
        assert terminal.acquired_at == 1  # Never rewritten by repeated polling.
        assert len(terminal.observations) == 1
    assert sum(v.get('retention_protected', False) for v in state.ingests['source'].records) == 3
    assert {v['acquired_at'] for v in state.ingests['source'].records
            if v.get('retention_protected', False)} == {1}
    with pytest.raises(RecoveryRequired):
        s.replay(oldest_cursor, now=10000)
    cursor = s._cursor(int(expected[0]['cursor'].split(':')[1]) - 1)
    assert s.replay(cursor, now=10000) == list(expected)
    path = s.path
    invalidated = deepcopy(state)
    _invalidate(invalidated)
    s.close()
    s = Storage(path)
    # Startup invalidation remains a deliberate new revision, not fake freshness.
    assert s.snapshot(now=10000)['projection'] == LocalAPI(invalidated.reducer).snapshot(now=10000)
    assert s.replay(expected[0]['cursor'], now=10000)[:-1] == list(expected)[1:]
    assert s.replay(expected[-1]['cursor'], now=10000)[0] == s.snapshot(now=10000)
    s.close()


def test_collision_discipline_on_both_sides_of_eviction_and_restart(tmp_path, monkeypatch):
    monkeypatch.setattr('workshop.retention.SEEN_LIMIT', 4)
    s = Storage(tmp_path / 'collision.db', initial=initial())
    for number in range(1, 7):
        emit(s, seq=number, at=number, id=str(number), revision=number)
    i = s.read().ingests['source']
    assert len(i._seen) == 4
    assert [key[-1] for key in i._seen] == ['3', '4', '5', '6']
    before = s.snapshot(now=100)
    with pytest.raises(ValueError, match='Changed content'):
        emit(s, seq=7, at=7, id='6', revision=7, state='failed')
    assert s.snapshot(now=100) == before
    assert emit(s, seq=6, at=7, id='6', revision=6).duplicates == 1
    # Evicted identity must execute EXACTLY the normal first-sighting path,
    # including ordering, provenance, terminal safety and collision checks.
    baseline = deepcopy(s.read().ingests['source'])
    payload = wire(id='1', revision=7, state='succeeded')
    assert baseline.cloudevents(payload, context=Acquisition(8, 8, 'boot')).accepted == 1
    assert s.cloudevents('source', payload, context=Acquisition(8, 8, 'boot'), source_cursor=7).accepted == 1
    actual = s.read().ingests['source']
    assert actual.records == baseline.records
    assert actual._seen == baseline._seen
    assert actual._ordering == baseline._ordering
    assert actual.reducer.executions == baseline.reducer.executions
    path = s.path
    s.close()
    s = Storage(path)
    before = s.snapshot(now=100)
    with pytest.raises(ValueError, match='Changed content'):
        emit(s, seq=8, at=9, id='1', revision=8, state='failed')
    assert s.snapshot(now=100) == before
    s.close()


def test_transitions_conflicts_correlation_audit_and_original_indices_survive(tmp_path):
    s = Storage(tmp_path / 'protected.db', initial=initial(), retention=8)
    emit(s, seq=1, at=1, id='first', state='starting')
    emit(s, seq=2, at=2, id='active', revision=2)
    conflict = json.loads(wire(id='conflict', revision=3))
    conflict['data']['session_id'] = 'conflicting-session'
    s.cloudevents('source', json.dumps(conflict).encode(), context=Acquisition(3, 3, 'boot'), source_cursor=3)
    emit(s, seq=4, at=4, id='terminal', revision=4, state='succeeded')
    saved = s.read()
    with s.transaction() as state:
        r = state.reducer
        r.add_correlation(ExecutionKey('alias', 'one'), KEY, mapping_version='retained-v1')
        r.alarms.register(rule())
        r.alarms.update('lost', True, now=4)
        r.alarms.acknowledge('1', actor='synthetic-operator', now=5)
    audit = deepcopy(s.read().reducer.alarms.audit)
    for number in range(5, RECORD_LIMIT + 25):
        # Terminal exact repeats are represented once, not clock-rebased.
        emit(s, seq=number, at=number, id=str(number), revision=number, state='succeeded')
    final = s.read()
    execution = final.reducer.executions[KEY]
    assert execution.discrepancies == saved.reducer.executions[KEY].discrepancies
    assert execution.observations == saved.reducer.executions[KEY].observations
    assert execution.observation_ids == [0, 1, 2, 3]
    assert execution.acquired_at == 4
    assert execution.lifecycle == saved.reducer.executions[KEY].lifecycle
    assert final.reducer.alarms.audit == audit
    assert final.reducer.correlations[ExecutionKey('alias', 'one')] == (KEY, 'retained-v1')
    assert [v['acquired_at'] for v in final.ingests['source'].records
            if v.get('retention_protected', False)] == [1, 2, 3, 4]
    assert len(final.ingests['source'].records) == RECORD_LIMIT
    before = s.retained_diagnostics()
    s.close()
    s = Storage(tmp_path / 'protected.db', retention=8)
    assert s.read().reducer.executions[KEY] == execution
    assert s.read().reducer.alarms.audit == audit
    assert s.retained_diagnostics()['records'] == before['records']
    s.close()


def test_protected_observation_capacity_rejects_atomically_instead_of_pruning(tmp_path, monkeypatch):
    monkeypatch.setattr('workshop.retention.OBSERVATION_LIMIT', 4)
    s = Storage(tmp_path / 'capacity.db', initial=initial())
    for number, lifecycle in enumerate(['starting', 'active', 'stopping', 'succeeded'], 1):
        emit(s, seq=number, at=number, id=str(number), revision=number, state=lifecycle)
    before = s.snapshot(now=10)
    conflict = wire(id='conflict', revision=5, state='failed')
    with pytest.raises(RetentionCapacityError, match='protected facts'):
        s.cloudevents('source', conflict, context=Acquisition(5, 5, 'boot'), source_cursor=5)
    assert s.snapshot(now=10) == before
    # Also test the in-memory reducer's feed/acquisition clocks on failure.
    detached = s.read().reducer
    saved = _pack(_sections(State(detached)))
    with pytest.raises(RetentionCapacityError):
        detached.observe_execution('agent', KEY, session='session', parent=None, task=None,
            lifecycle=Observation('failed', 'failed', 'new', 'urn:fixture:source', 'runtime', 5), acquired_at=5)
    assert _pack(_sections(State(detached))) == saved
    assert emit(s, seq=5, at=5, id='redundant', revision=5, state='succeeded').accepted == 1
    s.close()


def test_metadata_capacity_never_evicts_protected_facts(tmp_path, monkeypatch):
    monkeypatch.setattr('workshop.retention.RECORD_LIMIT', 3)
    s = Storage(tmp_path / 'metadata.db', initial=initial())
    for number in range(1, 4):
        emit(s, seq=number, at=number, id=str(number), native=str(number), state='succeeded')
    before = s.snapshot(now=10)
    with pytest.raises(RetentionCapacityError, match='Metadata capacity'):
        emit(s, seq=4, at=4, id='4', native='4', state='succeeded')
    assert s.snapshot(now=10) == before
    assert len(s.read().ingests['source']._seen) == 3
    s.close()


def test_snapshot_newer_key_path_uses_same_retirement_policy(tmp_path, monkeypatch):
    monkeypatch.setattr('workshop.retention.OBSERVATION_LIMIT', 5)
    s = Storage(tmp_path / 'snapshot.db', initial=initial(), retention=8)
    emit(s)
    for number in range(2, 20):
        token = s.begin_snapshot('source', generation=number, watermark=number-1,
            pages=('page',), complete=True, scope=('chat', 'cron'), acquired_at=number, epoch='boot')
        emit(s, seq=number, at=number+1, id=str(number), revision=number)
        s.snapshot_page(token, 'page', [domain(revision=number-1)])
        s.finish_snapshot(token)
    assert len(s.read().reducer.executions[KEY].observations) == 5
    assert s.replay(s._cursor(s._meta('revision')-1), now=30)[-1] == s.snapshot(now=30)
    s.close()


@pytest.mark.parametrize('mutation', ['replace', 'delete', 'reorder', 'splice', 'nested', 'types'])
def test_delta_codec_roundtrip_changes_only_and_order(mutation):
    before = {'one': initial().reducer.roles['agent'], 'two': [1, 2, 3], 'three': {KEY: {'x', 'y'}}}
    after = deepcopy(before)
    if mutation == 'replace':
        after['one'].complete = True
    elif mutation == 'delete':
        del after['three']
    elif mutation == 'reorder':
        after = dict(reversed(list(after.items())))
    elif mutation == 'splice':
        after['two'] = [0, 1, 3, 4]
    elif mutation == 'nested':
        after['one'].signals['admission'] = (Observation('on', 'enabled', 'v1', 'urn:source', 'f', 1), 2)
    else:
        after['two'] = (None, True, 1.5)
    patch = _unpack(_pack(difference(before, after, pack=_pack)))
    assert _pack(apply_difference(before, patch)) == _pack(after)
    assert _pack(before) != _pack(after)


def test_delta_randomized_roundtrips():
    rng = random.Random(1729)
    before = {'rows': [], 'map': {}}
    for number in range(100):
        after = deepcopy(before)
        after['map'][str(rng.randrange(8))] = [number, None, True]
        if number % 3 == 0 and after['map']:
            del after['map'][next(iter(after['map']))]
        after['rows'].append({'number': number})
        if len(after['rows']) > 7:
            del after['rows'][rng.randrange(7)]
        patch = _unpack(_pack(difference(before, after, pack=_pack)))
        assert _pack(apply_difference(before, patch)) == _pack(after)
        before = after


def test_v1_and_foreign_files_rejected_before_mutation(tmp_path):
    path = tmp_path / 'v1.db'
    # Read-only legacy fixture shape, not the installed historian.
    db = sqlite3.connect(path)
    db.execute('CREATE TABLE preserved(payload TEXT)')
    db.execute("INSERT INTO preserved VALUES ('historical evidence')")
    db.execute('PRAGMA application_id=1096239921')
    db.execute('PRAGMA user_version=1')
    db.commit()
    db.close()
    before = path.read_bytes()
    with pytest.raises(ValueError, match='supported Workshop-owned'):
        Storage(path)
    assert path.read_bytes() == before
    assert not Path(str(path)+'-wal').exists()


def test_process_change_without_lifecycle_change_survives_metadata_retirement(native, tmp_path, monkeypatch):
    from test_hermes_runtime import configured, sample, publish
    from workshop_collectors.hermes_work import ProcessSample
    monkeypatch.setattr('workshop.retention.RECORD_LIMIT', 8)
    observer, state = configured(native, probe=sample)
    s = Storage(tmp_path / 'process.db', initial=state, retention=8)
    publish(observer, s, at=1, seq=1)
    observer.work.process_probe = lambda pid: ProcessSample(pid, 'boot:1|22', 'Z')
    publish(observer, s, at=2, seq=2)
    observer.work.process_probe = sample
    for number in range(3, 25):
        publish(observer, s, at=number, seq=number)
    protected = [v for v in s.read().ingests['runtime'].records if v['retention_protected']]
    assert [v['attributes']['workshop.hermes.process'] for v in protected] == ['alive', 'not_alive', 'alive']
    assert [v['acquired_at'] for v in protected] == [1, 2, 3]
    assert len(s.read().ingests['runtime'].records) == 8
    s.close()
    s = Storage(tmp_path / 'process.db', retention=8)
    assert [v for v in s.read().ingests['runtime'].records if v['retention_protected']] == protected
    s.close()


@pytest.mark.parametrize('corroboration_only', [False, True])
def test_trace_span_correlation_metadata_survives_unchanged_lifecycle(tmp_path, monkeypatch, corroboration_only):
    from test_ingest import logs
    monkeypatch.setattr('workshop.retention.RECORD_LIMIT', 8)
    s = Storage(tmp_path / 'correlation.db', initial=initial(), retention=8)
    for number in range(1, 25):
        payload = logs(id=str(number), revision=number)
        record = payload['resourceLogs'][0]['scopeLogs'][0]['logRecords'][0]
        record['traceId'] = '11' * 16
        record['spanId'] = ('22' if number == 2 else '33') * 8
        if corroboration_only:
            record['attributes'] = [a for a in record['attributes'] if a['key'] != 'workshop.lifecycle']
        result = s.otlp('source', 'logs', json.dumps(payload).encode(),
                       context=Acquisition(number, number, 'boot'), source_cursor=number)
        assert (result.corroborated if corroboration_only else result.accepted) == 1
    protected = [v for v in s.read().ingests['source'].records if v['retention_protected']]
    assert [v['span_id'] for v in protected] == ['33' * 8, '22' * 8, '33' * 8]
    assert [v['acquired_at'] for v in protected] == [1, 2, 3]
    assert len(s.read().ingests['source'].records) == 8
    s.close()


def test_ignored_terminal_assertion_keeps_original_safe_domain_and_provenance(tmp_path, monkeypatch):
    monkeypatch.setattr('workshop.retention.RECORD_LIMIT', 8)
    s = Storage(tmp_path / 'ignored-terminal.db', initial=initial(), retention=8)
    emit(s, id='newer', revision=100)
    emit(s, seq=2, at=11, id='older-terminal', revision=2, state='succeeded')
    for number in range(3, 25):
        emit(s, seq=number, at=number+10, id=str(number), revision=100+number)
    records = s.read().ingests['source'].records
    saved = next(v for v in records if v['native_id'] == 'older-terminal')
    assert saved['domain']['lifecycle'] == 'succeeded'
    assert saved['domain']['revision'] == 2
    assert saved['acquired_at'] == 11
    assert saved['retention_protected']
    assert s.read().reducer.executions[KEY].lifecycle.mapped == 'active'
    s.close()


@pytest.mark.parametrize('retention', [2, 8, 33, 128])
def test_unchanged_audit_is_not_copied_into_deltas_and_every_window_has_anchor(tmp_path, retention):
    s = Storage(tmp_path / 'deltas.db', initial=initial(), retention=retention)
    with s.transaction() as state:
        state.reducer.alarms.register(rule())
        state.reducer.alarms.update('lost', True, now=1)
        state.reducer.alarms.acknowledge('1', actor='AUDIT_KEEP_ME', now=2)
    audit = deepcopy(s.read().reducer.alarms.audit)
    for _ in range(72):
        with s.transaction():
            pass
    rows = s._db.execute('SELECT revision,state FROM revisions ORDER BY revision').fetchall()
    assert len(rows) == min(retention, 74)
    assert _unpack(rows[0][1])['format'] == 'anchor-v2'
    anchors = 0
    for revision, payload in rows:
        value = _unpack(payload)
        if value['format'] == 'delta-v2':
            if revision > 2:  # Revision 2 creates the audit; only later calls are no-ops.
                assert value['value'] == ('same',)
                assert 'AUDIT_KEEP_ME' not in payload
        else:
            anchors += 1
    assert anchors <= (retention + ANCHOR_INTERVAL - 1) // ANCHOR_INTERVAL + 1
    assert s.read().reducer.alarms.audit == audit
    current = s.snapshot(now=100)
    assert s.replay(s._cursor(rows[0][0]-1), now=100)[-1] == current
    s.close()
