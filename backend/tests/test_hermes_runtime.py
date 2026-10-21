# SPDX-License-Identifier: Apache-2.0
"""A08/A10/A25 runtime path. Native writes below are fixture setup only."""
from dataclasses import replace
import inspect
import json
from pathlib import Path
import sqlite3

import pytest

from workshop.contracts import ExecutionKey, TaskKey
from workshop.ingest import Acquisition, Ingest, SourceBinding
from workshop.storage import RecoveryRequired, Storage
from test_hermes_work import native, collector, change, hashes, insert


def configured(native, *, probe=None, binding_change=None):
    from workshop_collectors.hermes_runtime import HermesRuntime, runtime_binding, initial_state
    work = collector(native, process_probe=probe)
    binding = runtime_binding(work.scope)
    if binding_change:
        binding = replace(binding, **binding_change)
    observer = HermesRuntime(work, binding)
    return observer, initial_state(binding, work.scope)


def sample(pid):
    from workshop_collectors.hermes_work import ProcessSample
    return ProcessSample(pid, 'boot:1|22', 'S')


def collect(observer, at=10):
    return observer.observe(board='synthetic-board', acquired_at=at)


def publish(observer, store, snapshot=None, *, at=10, seq=1, epoch='collector-1'):
    snapshot = snapshot or collect(observer, at)
    return observer.publish(store, 'runtime', snapshot, received_at=at,
                            epoch=epoch, source_cursor=seq)


def test_A08_A10_real_adapter_records_task_and_process_evidence_atomically(native, tmp_path):
    observer, state = configured(native, probe=sample)
    store = Storage(tmp_path / 'historian.db', initial=state)
    before = hashes(native)
    result = publish(observer, store)
    assert result.accepted == 1
    saved = store.read()
    binding = observer.binding
    key = ExecutionKey(binding.runtime, '1')
    execution = saved.reducer.executions[key]
    assert execution.task == TaskKey('synthetic-instance', 'synthetic-board', 'task')
    assert execution.lifecycle.mapped == 'active'
    assert execution.lifecycle.evidence_class == 'source_record'
    attrs = saved.ingests['runtime'].records[-1]['attributes']
    assert attrs['workshop.hermes.process'] == 'alive'
    assert attrs['workshop.execution.id'] == '1'
    assert attrs['workshop.hermes.mapping.version'] == 'hermes-runtime-v1'
    assert saved.source_cursors['runtime'] == 1
    assert hashes(native) == before
    assert saved.reducer.summary(binding.role, now=10)['availability'] == 'unknown'
    assert not saved.reducer.roles[binding.role].complete
    assert not store.snapshot(now=10)['projection']['native_write_enabled']
    store.close()


@pytest.mark.parametrize('probe', [None, lambda pid: None,
    lambda pid: (_ for _ in ()).throw(PermissionError()),
    lambda pid: (_ for _ in ()).throw(FileNotFoundError())])
def test_A08_runtime_unknown_stays_unknown(native, tmp_path, probe):
    observer, state = configured(native, probe=probe)
    store = Storage(tmp_path / 'historian.db', initial=state)
    snapshot = collect(observer)
    assert snapshot.observations()[0]['process'] == 'unknown'
    publish(observer, store, snapshot)
    attrs = store.read().ingests['runtime'].records[-1]['attributes']
    assert attrs['workshop.hermes.process'] == 'unknown'
    assert store.read().reducer.summary(observer.binding.role, now=10)['availability'] == 'unknown'
    store.close()


def test_A08_runtime_pid_reuse_does_not_prove_execution_or_terminal(native, tmp_path):
    from workshop_collectors.hermes_work import ProcessSample
    observer, state = configured(native, probe=lambda pid: ProcessSample(pid, 'boot:1|23', 'Z'))
    store = Storage(tmp_path / 'historian.db', initial=state)
    publish(observer, store)
    e = next(iter(store.read().reducer.executions.values()))
    assert e.lifecycle.mapped == 'active' and e.lifecycle.evidence_class == 'source_record'
    assert store.read().ingests['runtime'].records[-1]['attributes']['workshop.hermes.process'] == 'unknown'
    store.close()


@pytest.mark.parametrize('station', ['blocked', 'review'])
def test_A08_A25_attempt_exit_does_not_accept_task_or_stop_process(native, tmp_path, station):
    change(native, 'UPDATE tasks SET status=?', (station,))
    change(native, "UPDATE task_runs SET status='done',ended_at=8,outcome='completed'")
    observer, state = configured(native, probe=sample)
    before = hashes(native)
    store = Storage(tmp_path / 'historian.db', initial=state)
    snapshot = collect(observer)
    observation = snapshot.observations()[0]
    assert observation['process'] == 'alive'
    assert observation['task_station'] == station
    publish(observer, store, snapshot)
    saved = store.read()
    assert next(iter(saved.reducer.executions.values())).lifecycle.mapped == 'succeeded'
    assert saved.ingests['runtime'].records[-1]['attributes']['workshop.hermes.task.station'] == station
    assert hashes(native) == before
    store.close()


@pytest.mark.parametrize('status,outcome,ended,expected', [
    ('running', None, None, 'active'), ('done', 'completed', 8, 'succeeded'),
    ('done', 'failed', 8, 'failed'), ('done', 'cancelled', 8, 'cancelled'),
    ('done', 'blocked', 8, 'unknown'), ('done', 'novel', 8, 'unknown'),
    ('novel', None, None, 'unknown'), ('done', 'completed', None, 'unknown')])
def test_A08_attempt_mapping_closed_and_source_owned(native, status, outcome, ended, expected):
    change(native, 'UPDATE task_runs SET status=?,outcome=?,ended_at=?', (status, outcome, ended))
    observer, _ = configured(native, probe=sample)
    snapshot = collect(observer)
    record = snapshot.observations()[0]
    assert record['lifecycle'] == expected
    assert record['lifecycle_evidence'] == 'source_record'
    assert record['progress'] == 'unknown' and record['retry'] == 'not_requested'


@pytest.mark.parametrize('scopes', [(), (('other-instance', 'synthetic-board'),),
                                     (('synthetic-instance', 'other-board'),)])
def test_A10_runtime_ingress_denies_task_scope_and_rolls_back(native, tmp_path, scopes):
    observer, state = configured(native, probe=sample, binding_change={'task_scopes': scopes})
    store = Storage(tmp_path / 'historian.db', initial=state)
    before = store.snapshot(now=10)
    with pytest.raises(ValueError, match='scope'):
        publish(observer, store)
    assert store.snapshot(now=10) == before
    assert not store.read().source_cursors
    store.close()


def test_A10_runtime_binding_cannot_promote_process_to_lifecycle_authority(native):
    with pytest.raises(ValueError, match='source_record'):
        configured(native, binding_change={'evidence_class': 'runtime_observed'})


def test_A10_runtime_snapshot_cannot_be_rebound_to_other_instance(native, tmp_path):
    observer, state = configured(native, probe=sample)
    other, _ = configured(native, binding_change={'runtime': 'other-runtime'})
    store = Storage(tmp_path / 'historian.db', initial=state)
    before = store.snapshot(now=10)
    with pytest.raises(ValueError, match='binding'):
        other.publish(store, 'runtime', collect(observer), received_at=10,
                      epoch='collector-1', source_cursor=1)
    assert store.snapshot(now=10) == before
    store.close()


def test_A08_runtime_complete_native_tables_cannot_fabricate_atomic_watermark(native):
    observer, _ = configured(native, probe=sample)
    snapshot = collect(observer)
    assert snapshot.native_complete
    assert snapshot.native_event_cursor == 1
    assert snapshot.atomic_watermark is None
    assert snapshot.runtime_complete is False
    assert snapshot.runtime_coverage == 'partial'


def test_A08_runtime_restart_preserves_correlation_but_never_restores_online(native, tmp_path):
    observer, state = configured(native, probe=sample)
    path = tmp_path / 'historian.db'
    store = Storage(path, initial=state)
    publish(observer, store)
    store.close()
    store = Storage(path)
    saved = store.read()
    assert saved.ingests['runtime'].reconcile_required
    assert next(iter(saved.reducer.executions.values())).acquired_at is None
    assert next(iter(saved.reducer.executions.values())).task.native_id == 'task'
    assert saved.reducer.feeds[observer.binding.feed].last_acquired_at is None
    # Re-observation restores process metadata, not unsupported runtime availability.
    publish(observer, store, at=11, seq=2, epoch='collector-2')
    saved = store.read()
    assert saved.ingests['runtime'].reconcile_required
    assert saved.ingests['runtime'].records[-1]['attributes']['workshop.hermes.process'] == 'alive'
    assert next(iter(saved.reducer.executions.values())).acquired_at is None
    assert saved.reducer.summary(observer.binding.role, now=11)['availability'] == 'unknown'
    store.close()


def test_A08_runtime_retries_dedup_and_changed_cursor_identity_rejected(native, tmp_path):
    observer, state = configured(native, probe=sample)
    store = Storage(tmp_path / 'historian.db', initial=state)
    snapshot = collect(observer)
    publish(observer, store, snapshot)
    assert publish(observer, store, snapshot).duplicates == 1
    change(native, "UPDATE task_runs SET status='done',ended_at=11,outcome='completed'")
    before = store.snapshot(now=11)
    with pytest.raises(ValueError, match='identity'):
        publish(observer, store, collect(observer, 11), at=11)
    assert store.snapshot(now=11) == before
    publish(observer, store, collect(observer, 11), at=11, seq=2)
    assert next(iter(store.read().reducer.executions.values())).lifecycle.mapped == 'succeeded'
    with pytest.raises(RecoveryRequired):
        publish(observer, store, snapshot, at=12, seq=1)
    store.close()


def test_A08_runtime_truncation_never_deletes_unseen_and_cursor_not_event_id(native, tmp_path):
    observer, state = configured(native, probe=sample)
    store = Storage(tmp_path / 'historian.db', initial=state)
    publish(observer, store)
    change(native, "INSERT INTO task_runs (id,task_id,profile,status,started_at) VALUES (2,'task','coder','running',3)")
    observer.work.row_limit = 1
    snapshot = collect(observer, 11)
    assert not snapshot.native_complete
    assert snapshot.atomic_watermark is None
    publish(observer, store, snapshot, at=11, seq=2)
    assert len(store.read().reducer.executions) == 1
    assert store.read().source_cursors['runtime'] == 2
    assert snapshot.native_event_cursor == 1  # NOT used as the collector stream cursor
    store.close()


def test_A10_runtime_snapshot_privacy_and_detached_output(native, tmp_path):
    observer, state = configured(native, probe=sample)
    snapshot = collect(observer)
    observations = snapshot.observations()
    observations[0]['process'] = 'tampered'
    assert snapshot.observations()[0]['process'] == 'alive'
    store = Storage(tmp_path / 'historian.db', initial=state)
    publish(observer, store, snapshot)
    serialized = json.dumps(store.snapshot(now=10)) + repr(store.read().ingests['runtime'].records)
    for secret in ('private prompt', 'private comment', '/never/follow/this', 'cmdline', 'boot:1|22'):
        assert secret not in serialized
    store.close()


def test_A08_runtime_disconnect_does_not_commit_empty_inventory(native, tmp_path):
    observer, state = configured(native, probe=sample)
    store = Storage(tmp_path / 'historian.db', initial=state)
    publish(observer, store)
    before = store.snapshot(now=10)
    native.rename(native.with_suffix('.offline'))
    with pytest.raises(sqlite3.Error):
        collect(observer, 11)
    assert observer.quality(now=12) == 'disconnected'
    assert store.snapshot(now=10) == before
    native.with_suffix('.offline').rename(native)
    publish(observer, store, at=13, seq=2)
    assert observer.quality(now=14) == 'fresh'
    store.close()


def test_A08_runtime_supported_complete_recovery_is_explicit_fixture_only(native, tmp_path):
    # The live collector has no atomic runtime inventory. Exercise the standing
    # A08 contract with a separately configured, truly runtime-observed fixture.
    observer, state = configured(native)
    binding = replace(observer.binding, evidence_class='runtime_observed')
    state.ingests['runtime'] = Ingest(state.reducer, binding)
    store = Storage(tmp_path / 'historian.db', initial=state)
    domain = {'execution_id': '1', 'session_id': 'fixture-session', 'lifecycle': 'active',
              'task': {'source_instance': 'synthetic-instance', 'namespace': 'synthetic-board',
                       'native_id': 'task'}}
    token = store.begin_snapshot('runtime', generation=1, scope=('synthetic-board',),
        epoch='fixture-runtime', watermark=7, acquired_at=10, pages=('a',), complete=True)
    store.snapshot_page(token, 'a', [domain])
    store.finish_snapshot(token)
    assert store.read().source_cursors['runtime'] == 7
    assert store.read().reducer.roles[binding.role].complete
    store.close()
    store = Storage(tmp_path / 'historian.db')
    assert store.read().ingests['runtime'].reconcile_required
    domain['lifecycle'] = 'succeeded'
    token = store.begin_snapshot('runtime', generation=2, scope=('synthetic-board',),
        epoch='fixture-runtime', watermark=8, acquired_at=11, pages=('a',), complete=True)
    store.snapshot_page(token, 'a', [domain])
    store.finish_snapshot(token)
    assert not store.read().ingests['runtime'].reconcile_required
    assert next(iter(store.read().reducer.executions.values())).lifecycle.mapped == 'succeeded'
    assert store.read().reducer.summary(binding.role, now=11)['availability'] == 'unknown'
    store.close()


def test_A08_source_identity_survives_observer_and_service_restart(native, tmp_path):
    observer, state = configured(native, probe=sample)
    store = Storage(tmp_path / 'historian.db', initial=state)
    publish(observer, store)
    store.close()
    old = native.with_suffix('.old')
    native.rename(old)
    native.write_bytes(old.read_bytes())  # new inode, same reused task/run IDs
    observer, _ = configured(native, probe=sample)
    store = Storage(tmp_path / 'historian.db')
    before = store.snapshot(now=11)
    with pytest.raises(RecoveryRequired, match='identity'):
        publish(observer, store, at=11, seq=2, epoch='collector-2')
    assert store.snapshot(now=11) == before
    assert store.read().source_cursors['runtime'] == 1
    store.close()


def test_A08_process_change_without_board_event_is_new_durable_evidence(native, tmp_path):
    from workshop_collectors.hermes_work import ProcessSample
    observer, state = configured(native, probe=sample)
    store = Storage(tmp_path / 'historian.db', initial=state)
    first = collect(observer)
    publish(observer, store, first)
    observer.work.process_probe = lambda pid: ProcessSample(pid, 'boot:1|22', 'Z')
    second = collect(observer, 11)
    assert first.native_event_cursor == second.native_event_cursor
    publish(observer, store, second, at=11, seq=2)
    saved = store.read()
    assert [r['attributes']['workshop.hermes.process'] for r in saved.ingests['runtime'].records] == ['alive', 'not_alive']
    assert next(iter(saved.reducer.executions.values())).lifecycle.mapped == 'active'
    store.close()


def test_A25_runtime_public_surface_has_no_start_stop_install_control():
    from workshop_collectors.hermes_runtime import HermesRuntime
    assert {n for n, f in inspect.getmembers(HermesRuntime, inspect.isfunction)
            if not n.startswith('_')} == {'observe', 'publish', 'quality'}
