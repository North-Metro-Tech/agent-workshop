# SPDX-License-Identifier: Apache-2.0
"""Closing gate: integrated path on synthetic sources; actual live proof is opt-in."""
import ast
from dataclasses import replace
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from workshop.api import LocalAPI
from workshop.contracts import AlarmRule
from workshop.storage import Storage
from workshop_collectors.outbox import Outbox
from workshop_collectors.workflow import verify_agreement
from test_hermes_work import native, change, hashes
from test_hermes_runtime import configured, collect, sample


def deliver(observer, state, snapshot, tmp_path, at=10):
    store = Storage(tmp_path / 'historian.db', initial=state)
    q = Outbox(tmp_path / 'outbox.db', binding=observer.binding, clock_id='fixture-boot')
    q.enqueue(snapshot)
    q.deliver_one(store, received_at=at)
    q.close()
    return store


def test_A05_full_workflow_actual_silent_child_never_implies_progress(native, tmp_path):
    from workshop_collectors.hermes_work import linux_process_probe
    child = subprocess.Popen(['sleep', '30'])
    try:
        identity = linux_process_probe(child.pid)
        change(native, 'UPDATE task_runs SET worker_pid=?,worker_started_at=?',
               (child.pid, identity.fingerprint))
        change(native, "UPDATE task_events SET kind='on_session_end'")
        before = hashes(native)
        observer, state = configured(native, probe=linux_process_probe)
        snapshot = collect(observer)
        store = deliver(observer, state, snapshot, tmp_path)
        try:
            report = verify_agreement(observer, snapshot, store, now=10)
            row = report['comparisons'][0]
            assert row['process_at_acquisition'] == 'alive'
            assert row['progress'] == 'unknown' and row['tool_activity'] == 'unsupported'
            assert row['retry'] == 'not_requested'
            assert report['runtime_coverage'] == 'partial'
            assert hashes(native) == before and child.poll() is None
        finally:
            store.close()
    finally:
        child.terminate()
        child.wait(timeout=5)


@pytest.mark.parametrize('station', ['blocked', 'review'])
def test_A06_full_workflow_attempt_exit_station_and_local_ack_independent(native, tmp_path, station):
    change(native, 'UPDATE tasks SET status=?', (station,))
    change(native, "UPDATE task_runs SET status='done',ended_at=8,outcome='completed'")
    observer, state = configured(native, probe=sample)
    state.reducer.alarms.register(AlarmRule('fixture', 'work', 'fixture only', 'unknown',
        'inspect', 'soon', 'board', 'low', 'operator'))
    state.reducer.alarms.update('fixture', True, now=10)
    before = hashes(native)
    snapshot = collect(observer)
    store = deliver(observer, state, snapshot, tmp_path)
    try:
        initial = verify_agreement(observer, snapshot, store, now=10)
        alarm_id = store.read().reducer.alarms.occurrences[0].id
        LocalAPI(storage=store).acknowledge(alarm_id, now=11, authorized=True)
        after = verify_agreement(observer, snapshot, store, now=11)
        assert after['comparisons'] == initial['comparisons']
        row = after['comparisons'][0]
        assert row['native_task_station'] == station
        assert row['projected_lifecycle'] == 'succeeded'
        assert row['process_at_acquisition'] == 'alive'
        assert hashes(native) == before
    finally:
        store.close()


def test_A08_full_workflow_stop_queue_restore_preserves_partial_and_original_time(native, tmp_path):
    observer, state = configured(native, probe=sample)
    qpath, hpath = tmp_path / 'outbox.db', tmp_path / 'historian.db'
    store = Storage(hpath, initial=state)
    q = Outbox(qpath, binding=observer.binding, clock_id='fixture-boot')
    first = collect(observer)
    q.enqueue(first)
    q.deliver_one(store, received_at=10)
    q.enqueue(collect(observer, 11))
    q.close()
    store.close()
    # Restart, with one unacknowledged acquisition queued. Never restore live
    # freshness/availability from disk; old queue receipt cannot refresh it.
    store = Storage(hpath)
    assert store.read().ingests['runtime'].reconcile_required
    assert next(iter(store.read().reducer.executions.values())).acquired_at is None
    q = Outbox(qpath, binding=observer.binding, clock_id='fixture-boot')
    q.deliver_one(store, received_at=1000)
    report = verify_agreement(observer, observer.observe(board='synthetic-board', acquired_at=11), store, now=1000)
    assert report['role_availability'] == 'unknown'
    assert report['runtime_coverage'] == 'partial'
    assert store.read().ingests['runtime'].reconcile_required
    assert not store.read().reducer.roles[observer.binding.role].complete
    assert store.read().reducer.feed_quality(observer.binding.feed, now=1000) == 'unknown'
    assert next(iter(store.read().reducer.executions.values())).acquired_at is None
    q.close()
    store.close()


def test_A10_full_workflow_empty_task_scope_denies_same_data_without_ack(native, tmp_path):
    observer, _ = configured(native, probe=sample)
    actual = collect(observer)
    denied, state = configured(native, binding_change={'task_scopes': ()})
    queue = Outbox(tmp_path / 'outbox.db', binding=denied.binding, clock_id='fixture-boot')
    queue.enqueue(replace(actual, binding=denied.binding))
    store = Storage(tmp_path / 'historian.db', initial=state)
    before = store.snapshot(now=10)
    with pytest.raises(ValueError, match='scope'):
        queue.deliver_one(store, received_at=10)
    assert queue.status()['pending'] == 1
    assert store.snapshot(now=10) == before
    assert not store.read().source_cursors
    queue.close()
    store.close()


def test_gate_comparator_rejects_mismatched_projection(native, tmp_path):
    observer, state = configured(native)
    snapshot = collect(observer)
    store = deliver(observer, state, snapshot, tmp_path)
    with store.transaction() as saved:
        next(iter(saved.reducer.executions.values())).task = None
    with pytest.raises(ValueError, match='disagreement'):
        verify_agreement(observer, snapshot, store, now=10)
    store.close()


def test_gate_cannot_verify_an_undelivered_acquisition(native, tmp_path):
    observer, state = configured(native)
    store = deliver(observer, state, collect(observer), tmp_path)
    later = collect(observer, 20)
    with pytest.raises(ValueError, match='acquisition'):
        verify_agreement(observer, later, store, now=20)
    store.close()


@pytest.mark.parametrize('field,value', [('attempt_status', 'failed'), ('attempt_outcome', 'cancelled')])
def test_gate_independently_compares_native_labels(native, tmp_path, field, value):
    observer, state = configured(native)
    original = collect(observer)
    rows = original.observations()
    rows[0][field] = value
    altered = replace(original, _observations_json=json.dumps(rows))
    store = deliver(observer, state, altered, tmp_path)
    with pytest.raises(ValueError, match='disagreement'):
        verify_agreement(observer, altered, store, now=10)
    store.close()


def test_phase2_interlock_closed_collector_imports_and_no_domain_clock():
    root = Path(__file__).parents[2] / 'collectors' / 'workshop_collectors'
    allowed = {'contextlib', 'copy', 'dataclasses', 'json', 'pathlib', 're', 'sqlite3',
               'tempfile', 'uuid', 'workshop.contracts', 'workshop.freshness',
               'workshop.ingest', 'workshop.reducer', 'workshop.storage'}
    for path in root.glob('*.py'):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(a.name in allowed for a in node.names), path
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                assert node.module in allowed, path
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in {'exec', 'eval', '__import__'}, path
    from workshop_collectors.hermes_work import HermesWork
    from workshop_collectors.hermes_runtime import HermesRuntime
    import inspect
    expected = {HermesWork: {'observe', 'quality'}, HermesRuntime: {'observe', 'publish', 'quality'},
                Outbox: {'enqueue', 'deliver_one', 'status', 'close'}}
    for cls, names in expected.items():
        assert {n for n, f in inspect.getmembers(cls, inspect.isfunction) if not n.startswith('_')} == names


def test_collector_demo_deterministic_and_plainly_synthetic():
    from workshop_collectors.demo import snapshot
    first, second = snapshot(), snapshot()
    assert first == second
    assert first['synthetic_only'] and not first['actual_live_observation']
    assert first['native_write_enabled'] is False
    assert first['runtime_coverage'] == 'partial'
    assert first['role_availability'] == 'unknown'
    assert first['feed_quality_at_delivery'] == 'disconnected'
    assert {r['native_task_station'] for r in first['comparisons']} == {'running', 'blocked', 'review'}


def test_collector_clean_commands_and_no_implicit_live_reads(tmp_path):
    root = Path(__file__).parents[2]
    checkout = tmp_path / 'clean checkout'
    checkout.mkdir()
    for name in ('backend', 'collectors', 'scripts'):
        shutil.copytree(root / name, checkout / name, ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache'))
    shutil.copy(root / 'pytest.ini', checkout / 'pytest.ini')
    env = dict(os.environ)
    env.pop('PYTHONPATH', None)
    outputs = []
    for command in ([sys.executable, 'scripts/dev.py', 'install'],
                    [sys.executable, 'scripts/dev.py', 'collector-demo'],
                    [str(checkout / '.venv/bin/python'), '-m', 'workshop_collectors.demo'],
                    [sys.executable, 'scripts/dev.py', 'check'],
                    [sys.executable, 'scripts/dev.py', 'test', 'backend/tests/test_outbox.py', '-q']):
        result = subprocess.run(command, cwd=checkout, env=env, capture_output=True, text=True, timeout=60)
        assert result.returncode == 0, result.stdout + result.stderr
        if command[-1] in ('collector-demo', 'workshop_collectors.demo'):
            outputs.append(json.loads(result.stdout))
    assert len(outputs) == 2 and outputs[0] == outputs[1]
    assert not (checkout / '.workshop-state').exists()
    result = subprocess.run([sys.executable, 'scripts/observe_workflow.py'], cwd=checkout,
                            env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 2 and 'requires --approved-local' in result.stderr
    assert not (checkout / '.workshop-state').exists()


def test_workflow_entrypoint_isolated_actual_path_and_restart(native, tmp_path, monkeypatch, capsys):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[2] / 'scripts'))
    import observe_workflow
    monkeypatch.setattr(observe_workflow, 'ROOT', tmp_path)
    observer, _ = configured(native)
    monkeypatch.setattr(observe_workflow, 'approved_scope', lambda: observer.work.scope)
    monkeypatch.setattr(sys, 'argv', ['observe_workflow.py', '--approved-local'])
    for reopened in (False, True):
        observe_workflow.main()
        report = json.loads(capsys.readouterr().out)
        assert report['source_projection_agreement'] and report['compared_attempts'] == 1
        assert report['historian']['reopened'] is reopened
        assert report['task_scope_denial']['empty_scope_denied']
        assert report['native_fence']['unchanged']
        assert report['runtime_coverage'] == 'partial'
    change(native, 'DELETE FROM task_runs')
    with pytest.raises(RuntimeError, match='current.*attempt'):
        observe_workflow.main()


def test_A25_full_workflow_uninstall_restore_retains_pending_outbox_native_independent(native, tmp_path):
    """Real silent OS child; isolated source install and synthetic tasks/schedules.
    A queued acquisition survives stop + removal of code, then drains on restore.
    Only the TEST owns child termination. The product never sees the schedule.
    """
    from workshop_collectors.hermes_work import linux_process_probe
    child = subprocess.Popen(['sleep', '60'])
    root = Path(__file__).parents[2]
    deployment = tmp_path / 'disposable-workshop'
    retained = tmp_path / 'retained-workshop-state'
    retained.mkdir()
    schedule = tmp_path / 'synthetic-native-schedules.json'
    schedule.write_text('{"native_jobs":["unchanged"]}')
    schedule_before = schedule.read_bytes()
    try:
        change(native, 'UPDATE task_runs SET worker_pid=?,worker_started_at=?',
               (child.pid, linux_process_probe(child.pid).fingerprint))
        before = hashes(native)
        def install():
            deployment.mkdir()
            for name in ('backend', 'collectors', 'scripts'):
                shutil.copytree(root / name, deployment / name,
                    ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache', 'tests'))
            (deployment / 'probe.py').write_text('''from pathlib import Path
import sys
from workshop.storage import Storage
from workshop_collectors.base import SourceScope
from workshop_collectors.hermes_work import HermesWork, linux_process_probe
from workshop_collectors.hermes_runtime import HermesRuntime, runtime_binding, initial_state
from workshop_collectors.outbox import Outbox
native, retained = map(Path, sys.argv[1:3])
scope = SourceScope('synthetic-instance', 'synthetic-board', native, ('coder', 'vitruvius-core'))
binding = runtime_binding(scope)
observer = HermesRuntime(HermesWork(scope, process_probe=linux_process_probe), binding)
queue = Outbox(retained/'outbox.db', binding=binding, clock_id='fixture-boot')
if sys.argv[3] == 'enqueue':
    snapshot = observer.observe(board=scope.board, acquired_at=10)
    assert snapshot.observations()[0]['process'] == 'alive'
    queue.enqueue(snapshot)
    assert queue.status()['pending'] == 1
else:
    store = Storage(retained/'historian.db', initial=initial_state(binding, scope))
    assert queue.status()['pending'] == 1
    assert queue.deliver_one(store, received_at=100).accepted == 1
    assert queue.status()['pending'] == 0
    assert store.read().reducer.summary(binding.role, now=100)['availability'] == 'unknown'
    assert store.snapshot(now=100)['projection']['native_write_enabled'] is False
    store.close()
queue.close()
print('isolated full-path proof passed')
''')
            env = dict(os.environ)
            env.pop('PYTHONPATH', None)
            result = subprocess.run([sys.executable, 'scripts/dev.py', 'install'], cwd=deployment,
                                    env=env, capture_output=True, text=True, timeout=60)
            assert result.returncode == 0, result.stdout + result.stderr
            return env
        def run(mode, env):
            result = subprocess.run([str(deployment / '.venv/bin/python'), 'probe.py',
                str(native), str(retained), mode], cwd=deployment, env=env,
                capture_output=True, text=True, timeout=30)
            assert result.returncode == 0, result.stdout + result.stderr
        run('enqueue', install())
        assert child.poll() is None and hashes(native) == before
        shutil.rmtree(deployment)
        assert not deployment.exists() and (retained / 'outbox.db').exists()
        assert child.poll() is None and hashes(native) == before and schedule.read_bytes() == schedule_before
        run('drain', install())
        assert child.poll() is None and hashes(native) == before and schedule.read_bytes() == schedule_before
    finally:
        child.terminate()
        child.wait(timeout=5)
