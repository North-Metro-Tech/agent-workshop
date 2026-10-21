# SPDX-License-Identifier: Apache-2.0
"""Runtime-path regression and isolated deployment A25, never native mutation."""
from dataclasses import replace
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from workshop.contracts import ExecutionKey
from workshop.ingest import Acquisition, Ingest
from workshop.storage import Storage
from test_hermes_work import native, change, hashes
from test_hermes_runtime import configured, sample, collect, publish


def payload(observer, at=10):
    return json.loads(collect(observer, at)._payload('collector-1', 1))


def log_attributes(wire):
    return wire['resourceLogs'][0]['scopeLogs'][0]['logRecords'][0]['attributes']


def test_A10_process_only_corroboration_still_enforces_task_allowlist(native, tmp_path):
    observer, state = configured(native, binding_change={'task_scopes': ()})
    wire = payload(observer)
    attrs = log_attributes(wire)
    attrs[:] = [a for a in attrs if a['key'] != 'workshop.lifecycle']
    store = Storage(tmp_path / 'historian.db', initial=state)
    before = store.snapshot(now=10)
    with pytest.raises(ValueError, match='scope'):
        store.otlp('runtime', 'logs', json.dumps(wire).encode(),
                   context=Acquisition(10, 10, 'collector-1'), source_cursor=1)
    assert store.snapshot(now=10) == before
    assert not store.read().source_cursors
    store.close()


@pytest.mark.parametrize('field,value', [
    ('workshop.hermes.process', {'stringValue': 'PRIVATE_PROCESS_TEXT'}),
    ('workshop.hermes.process.reason', {'stringValue': 'PRIVATE_COMMAND_TEXT'}),
    ('workshop.hermes.board.event_id', {'boolValue': True}),
    ('workshop.hermes.native.complete', {'intValue': 1}),
    ('workshop.hermes.mapping.version', {'stringValue': 'unreviewed-v2'}),
    ('workshop.hermes.process', None),
])
def test_A10_corrupt_process_metadata_rolls_back_entire_batch(native, tmp_path, field, value):
    observer, state = configured(native, probe=sample)
    wire = payload(observer)
    attrs = log_attributes(wire)
    attrs[:] = [a for a in attrs if a['key'] != field]
    if value is not None:
        attrs.append({'key': field, 'value': value})
    store = Storage(tmp_path / 'historian.db', initial=state)
    before = store.snapshot(now=10)
    with pytest.raises(ValueError):
        store.otlp('runtime', 'logs', json.dumps(wire).encode(),
                   context=Acquisition(10, 10, 'collector-1'), source_cursor=1)
    assert store.snapshot(now=10) == before
    store.close()


@pytest.mark.parametrize('state', ['Z', 'X', 'x'])
def test_A08_dead_matching_process_cannot_fabricate_terminal_attempt(native, tmp_path, state):
    from workshop_collectors.hermes_work import ProcessSample
    observer, initial = configured(native, probe=lambda pid: ProcessSample(pid, 'boot:1|22', state))
    store = Storage(tmp_path / 'historian.db', initial=initial)
    snapshot = collect(observer)
    assert snapshot.observations()[0]['process'] == 'not_alive'
    publish(observer, store, snapshot)
    execution = next(iter(store.read().reducer.executions.values()))
    assert execution.lifecycle.mapped == 'active'
    assert execution.lifecycle.evidence_class == 'source_record'
    store.close()


def test_A08_complete_source_record_snapshot_cannot_clear_restart_latch(native, tmp_path):
    observer, state = configured(native, probe=sample)
    store = Storage(tmp_path / 'historian.db', initial=state)
    publish(observer, store)
    store.close()
    store = Storage(tmp_path / 'historian.db')
    # Even an explicitly supplied fixture watermark and all native tables do
    # not turn source_record lifecycle into runtime-observed coverage.
    token = store.begin_snapshot('runtime', generation=1, scope=('synthetic-board',),
        epoch='collector-1', watermark=1, acquired_at=11, pages=('a',), complete=True)
    store.snapshot_page(token, 'a', [{'execution_id': '1', 'session_id': 'kanban-attempt/1',
        'lifecycle': 'active', 'task': {'source_instance': 'synthetic-instance',
         'namespace': 'synthetic-board', 'native_id': 'task'}}])
    store.finish_snapshot(token)
    saved = store.read()
    assert saved.ingests['runtime'].reconcile_required
    assert not saved.reducer.roles[observer.binding.role].complete
    assert next(iter(saved.reducer.executions.values())).acquired_at is None
    store.close()


def test_A10_identical_attempt_task_ids_across_scopes_remain_distinct(native, tmp_path):
    from workshop_collectors.hermes_work import HermesWork
    from workshop_collectors.hermes_runtime import HermesRuntime, runtime_binding, initial_state
    first, state = configured(native, probe=sample)
    second_scope = replace(first.work.scope, source_instance='other-instance', board='other-board')
    second = HermesRuntime(HermesWork(second_scope, process_probe=sample), runtime_binding(second_scope))
    other_state = initial_state(second.binding, second_scope)
    state.reducer.roles.update(other_state.reducer.roles)
    state.reducer.feeds.update(other_state.reducer.feeds)
    state.ingests['other'] = Ingest(state.reducer, second.binding)
    store = Storage(tmp_path / 'historian.db', initial=state)
    publish(first, store)
    second.publish(store, 'other', second.observe(board='other-board', acquired_at=10),
                   received_at=10, epoch='collector-1', source_cursor=1)
    saved = store.read()
    assert len(saved.reducer.executions) == 2
    assert len({e.task for e in saved.reducer.executions.values()}) == 2
    assert len({e.key.runtime for e in saved.reducer.executions.values()}) == 2
    store.close()


@pytest.mark.parametrize('sequence', [0, -1, True, 2**63, '1'])
def test_A08_runtime_source_sequence_is_explicit_and_bounded(native, tmp_path, sequence):
    observer, state = configured(native)
    store = Storage(tmp_path / 'historian.db', initial=state)
    before = store.snapshot(now=10)
    with pytest.raises(ValueError):
        publish(observer, store, seq=sequence)
    assert store.snapshot(now=10) == before
    store.close()


def test_A08_delayed_snapshot_cannot_gain_freshness_from_receipt(native, tmp_path):
    observer, state = configured(native, probe=sample)
    store = Storage(tmp_path / 'historian.db', initial=state)
    snapshot = collect(observer)
    observer.publish(store, 'runtime', snapshot, received_at=1000,
                     epoch='collector-1', source_cursor=1)
    saved = store.read()
    assert next(iter(saved.reducer.executions.values())).acquired_at == 10
    assert saved.reducer.feed_quality(observer.binding.feed, now=1000) == 'disconnected'
    assert saved.ingests['runtime'].records[-1]['received_at'] == 1000
    store.close()


def test_A08_bound_source_identity_cannot_be_omitted(native, tmp_path):
    from workshop.storage import RecoveryRequired
    observer, state = configured(native, probe=sample)
    store = Storage(tmp_path / 'historian.db', initial=state)
    snapshot = collect(observer)
    publish(observer, store, snapshot)
    before = store.snapshot(now=10)
    with pytest.raises(RecoveryRequired, match='identity'):
        store.otlp('runtime', 'logs', snapshot._payload('collector-1', 2),
                   context=Acquisition(10, 10, 'collector-1'), source_cursor=2)
    assert store.snapshot(now=10) == before
    store.close()


def test_A08_legacy_unproven_source_cannot_silently_bind_existing_history(native, tmp_path):
    from workshop.storage import RecoveryRequired
    observer, state = configured(native, probe=sample)
    store = Storage(tmp_path / 'historian.db', initial=state)
    snapshot = collect(observer)
    store.otlp('runtime', 'logs', snapshot._payload('collector-1', 1),
               context=Acquisition(10, 10, 'collector-1'), source_cursor=1)
    before = store.snapshot(now=10)
    with pytest.raises(RecoveryRequired, match='identity'):
        publish(observer, store, snapshot, seq=2)
    assert store.snapshot(now=10) == before
    assert not store.read().source_identities
    store.close()


@pytest.mark.parametrize('identity', [[], ('a', 1), (True, 1), (1,), (-1, 1)])
def test_A08_malformed_source_identity_rolls_back(native, tmp_path, identity):
    observer, state = configured(native)
    store = Storage(tmp_path / 'historian.db', initial=state)
    before = store.snapshot(now=10)
    with pytest.raises(ValueError, match='identity'):
        publish(observer, store, replace(collect(observer), source_identity=identity))
    assert store.snapshot(now=10) == before
    assert not store.read().source_identities
    store.close()


def test_A25_stop_uninstall_restore_isolated_deployment_native_child_tasks_schedules_unchanged(native, tmp_path):
    """Real OS child; synthetic native stores. Test alone owns child lifecycle.

    One-shot observer exits normally; remove ONLY the copied Workshop deployment,
    then restore it. Native child and native store live outside that deployment.
    No observer code ever receives the native schedule path or child controls.
    """
    from workshop_collectors.hermes_work import linux_process_probe
    child = subprocess.Popen([sys.executable, '-c', 'import sys; sys.stdin.read()'], stdin=subprocess.PIPE)
    root = Path(__file__).parents[2]
    deployment = tmp_path / 'disposable-workshop'
    historian = tmp_path / 'historian.db'
    schedule = tmp_path / 'synthetic-native-schedules.json'
    schedule.write_text(json.dumps({'jobs': [{'id': 'native-job', 'schedule': 'unchanged'}]}))
    before_schedule = schedule.read_bytes()
    try:
        fingerprint = linux_process_probe(child.pid).fingerprint
        change(native, 'UPDATE task_runs SET worker_pid=?,worker_started_at=?', (child.pid, fingerprint))
        before = hashes(native)
        def install():
            deployment.mkdir()
            shutil.copytree(root / 'backend' / 'workshop', deployment / 'backend' / 'workshop',
                            ignore=shutil.ignore_patterns('__pycache__'))
            shutil.copytree(root / 'collectors', deployment / 'collectors',
                            ignore=shutil.ignore_patterns('__pycache__'))
            (deployment / 'scripts').mkdir()
            shutil.copy(root / 'scripts' / 'dev.py', deployment / 'scripts' / 'dev.py')
            (deployment / 'probe.py').write_text('''from pathlib import Path
from workshop_collectors.base import SourceScope
from workshop_collectors.hermes_work import HermesWork, linux_process_probe
from workshop_collectors.hermes_runtime import HermesRuntime, runtime_binding, initial_state
from workshop.storage import Storage
import json, sys
native, historian = map(Path, sys.argv[1:3])
scope = SourceScope('synthetic-instance', 'synthetic-board', native, ('coder', 'vitruvius-core'))
binding = runtime_binding(scope)
observer = HermesRuntime(HermesWork(scope, process_probe=linux_process_probe), binding)
store = Storage(historian, initial=initial_state(binding, scope)) if not historian.exists() else Storage(historian)
seq = store.read().source_cursors.get('runtime', 0) + 1
snapshot = observer.observe(board=scope.board, acquired_at=10 + seq)
observer.publish(store, 'runtime', snapshot, received_at=10 + seq, epoch='restored-' + str(seq), source_cursor=seq)
saved = store.read()
assert snapshot.observations()[0]['process'] == 'alive'
assert len(saved.reducer.executions) == 1
assert saved.reducer.summary(binding.role, now=10+seq)['availability'] == 'unknown'
print(json.dumps({'observations': len(snapshot.observations()), 'native_write_enabled': False, 'sequence': seq}))
store.close()
''')
            env = dict(os.environ)
            env.pop('PYTHONPATH', None)
            result = subprocess.run([sys.executable, 'scripts/dev.py', 'install'], cwd=deployment,
                                    env=env, text=True, capture_output=True, timeout=60)
            assert result.returncode == 0, result.stdout + result.stderr
            return env
        def observe(env, seq):
            result = subprocess.run([str(deployment / '.venv/bin/python'), 'probe.py',
                str(native), str(historian)], cwd=deployment, env=env,
                text=True, capture_output=True, timeout=30)
            assert result.returncode == 0, result.stdout + result.stderr
            assert json.loads(result.stdout)['sequence'] == seq
        observe(install(), 1)
        assert child.poll() is None  # stop observer: process exited, native still alive
        assert hashes(native) == before and schedule.read_bytes() == before_schedule
        shutil.rmtree(deployment)  # uninstall ONLY the test's source-only deployment
        assert not deployment.exists() and historian.exists()
        assert child.poll() is None
        assert hashes(native) == before and schedule.read_bytes() == before_schedule
        observe(install(), 2)
        assert child.poll() is None
        assert hashes(native) == before and schedule.read_bytes() == before_schedule
        store = Storage(historian)
        assert store.read().source_cursors['runtime'] == 2
        assert len(store.read().reducer.executions) == 1
        assert store.read().ingests['runtime'].reconcile_required
        store.close()
    finally:
        child.stdin.close()  # test cleanup, NOT observer control
        child.wait(timeout=5)
