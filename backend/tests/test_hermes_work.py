# SPDX-License-Identifier: Apache-2.0
"""A05/A06/A10: synthetic stores only; live evidence is a separate opt-in script."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess

import pytest

# Independent installed-schema fixture, including migration-added completion_contract.
COLUMNS = {
    'tasks': 'id:T title:T body:T assignee:T status:T priority:I created_by:T created_at:I started_at:I completed_at:I workspace_kind:T workspace_path:T branch_name:T project_id:T claim_lock:T claim_expires:I tenant:T result:T idempotency_key:T consecutive_failures:I worker_pid:I worker_started_at:I last_failure_error:T max_runtime_seconds:I last_heartbeat_at:I current_run_id:I workflow_template_id:T current_step_key:T skills:T model_override:T provider_override:T reasoning_effort:T max_retries:I goal_mode:I goal_max_turns:I session_id:T block_kind:T block_recurrences:I completion_contract:T',
    'task_runs': 'id:I task_id:T profile:T step_key:T status:T claim_lock:T claim_expires:I worker_pid:I worker_started_at:I max_runtime_seconds:I last_heartbeat_at:I started_at:I ended_at:I outcome:T summary:T metadata:T error:T',
    'task_events': 'id:I task_id:T run_id:I kind:T payload:T created_at:I',
    'task_comments': 'id:I task_id:T author:T body:T created_at:I',
    'task_attachments': 'id:I task_id:T filename:T stored_path:T content_type:T size:I uploaded_by:T created_at:I',
    'task_links': 'parent_id:T child_id:T',
}


def insert(db, table, **row):
    db.execute('INSERT INTO ' + table + ' (' + ','.join(row) + ') VALUES ('
               + ','.join('?' for _ in row) + ')', tuple(row.values()))


@pytest.fixture
def native(tmp_path):
    path = tmp_path / 'synthetic.db'
    db = sqlite3.connect(path)
    for table, columns in COLUMNS.items():
        db.execute('CREATE TABLE ' + table + ' (' + ','.join(
            name + ' ' + {'T': 'TEXT', 'I': 'INTEGER'}[kind]
            for name, kind in (c.split(':') for c in columns.split())) + ')')
    insert(db, 'tasks', id='task', title='Synthetic', body='private prompt', assignee='coder',
           status='running', priority=1, created_at=1, current_run_id=1)
    insert(db, 'task_runs', id=1, task_id='task', profile='coder', status='running',
           worker_pid=123, worker_started_at='boot:1|22', started_at=2)
    insert(db, 'task_events', id=1, task_id='task', run_id=1, kind='spawned',
           payload=json.dumps({'pid': 123, 'started_at': 'boot:1|22', 'cmdline': 'secret'}), created_at=2)
    insert(db, 'task_comments', id=1, task_id='task', author='coder', body='private comment', created_at=3)
    insert(db, 'task_attachments', id=1, task_id='task', filename='evidence.txt',
           stored_path='/never/follow/this', size=2, created_at=3)
    db.commit()
    db.close()
    return path


def collector(native, **kwargs):
    from workshop_collectors.base import SourceScope
    from workshop_collectors.hermes_work import HermesWork
    return HermesWork(SourceScope('synthetic-instance', 'synthetic-board', native,
                                 ('coder', 'vitruvius-core')), **kwargs)


def snap(native, **kwargs):
    return collector(native, **kwargs).observe(board='synthetic-board', acquired_at=10)


def change(native, sql, params=()):
    db = sqlite3.connect(native)
    db.execute(sql, params)
    db.commit()
    db.close()


def hashes(path):
    db = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
    try:
        schema = list(db.execute('SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name'))
    finally:
        db.close()
    return hashlib.sha256(path.read_bytes()).hexdigest(), hashlib.sha256(repr(schema).encode()).hexdigest()


def test_A10_scope_mandatory_exact_path_and_board(native):
    c = collector(native)
    with pytest.raises(ValueError, match='board'):
        c.observe(board='other', acquired_at=10)
    from workshop_collectors.hermes_work import approved_scope
    with pytest.raises(ValueError, match='approved'):
        approved_scope(path=native)
    s = snap(native)
    assert s.source_instance == 'synthetic-instance'
    assert s.board == 'synthetic-board'
    assert s.latest_event_id == 1
    assert s.complete
    assert s.runtime_coverage == 'partial'


@pytest.mark.parametrize('surface', ['board_view', 'task_detail', 'workers', 'run', 'inspect'])
def test_A10_each_surface_native_bytes_schema_unchanged(native, surface):
    before = hashes(native)
    s = snap(native)
    args = () if surface in ('board_view', 'workers') else ('task',) if surface == 'task_detail' else (1,)
    value = getattr(s, surface)(*args)
    assert value is not None
    assert hashes(native) == before
    assert 'private prompt' not in repr(value)
    assert 'private comment' not in repr(value)
    assert '/never/follow/this' not in repr(value)
    assert 'cmdline' not in repr(value)


def test_A10_detail_grouping_links_runs_and_privacy(native):
    insert_db = sqlite3.connect(native)
    insert(insert_db, 'tasks', id='child', title='Child', assignee='coder', status='review', created_at=2)
    insert(insert_db, 'task_links', parent_id='task', child_id='child')
    insert_db.commit()
    insert_db.close()
    s = snap(native)
    assert s.board_view()['columns']['review'][0]['id'] == 'child'
    detail = s.task_detail('task')
    assert detail['links'] == {'parents': [], 'children': ['child']}
    assert len(detail['comments']) == len(detail['events']) == len(detail['attachments']) == len(detail['runs']) == 1
    assert detail['task']['body'] is None
    assert detail['events'][0]['payload'] is None
    assert detail['attachments'][0]['stored_path'] is None
    assert s.workers()['count'] == 1
    assert s.workers()['evidence_class'] == 'source_record'
    detail['task']['status'] = 'done'
    assert s.task_detail('task')['task']['status'] == 'running'


def test_A10_exact_schema_no_views_hidden_or_unknown_columns(native):
    change(native, 'ALTER TABLE tasks ADD COLUMN unexpected TEXT')
    with pytest.raises(ValueError, match='schema'):
        snap(native)


def test_A10_view_refused(native):
    change(native, 'ALTER TABLE task_runs RENAME TO original_runs')
    change(native, 'CREATE VIEW task_runs AS SELECT * FROM original_runs')
    with pytest.raises(ValueError, match='table'):
        snap(native)


def test_A10_snapshot_and_watermark_share_one_transaction(native, monkeypatch):
    # Hook the bounded row reader after the snapshot's MAX(event.id) has established its read view.
    from workshop_collectors.base import ReadTransaction
    change(native, 'PRAGMA journal_mode=WAL')
    original = ReadTransaction.rows
    fired = False
    def race(self, table):
        nonlocal fired
        if not fired:
            fired = True
            writer = sqlite3.connect(native)
            writer.execute("UPDATE tasks SET status='review' WHERE id='task'")
            insert(writer, 'task_events', id=2, task_id='task', kind='review', created_at=4)
            writer.commit()
            writer.close()
        return original(self, table)
    monkeypatch.setattr(ReadTransaction, 'rows', race)
    s = snap(native)
    assert s.latest_event_id == 1
    assert s.task_detail('task')['task']['status'] == 'running'
    s2 = snap(native)
    assert s2.latest_event_id == 2
    assert s2.task_detail('task')['task']['status'] == 'review'


def test_A10_row_bound_partial_never_claims_runtime_complete(native):
    s = snap(native, row_limit=1)
    assert not s.truncated_tables
    change(native, "INSERT INTO tasks (id,assignee,status) VALUES ('other','coder','running')")
    s = snap(native, row_limit=1)
    assert s.truncated_tables == ('tasks',)
    assert not s.complete
    assert s.runtime_coverage == 'partial'


@pytest.mark.parametrize('kind', ['oversized', 'aggregate', 'blob', 'nonfinite'])
def test_A10_bad_or_overbudget_record_no_partial_publish(native, kind):
    kwargs = {}
    if kind == 'oversized':
        change(native, 'UPDATE tasks SET body=?', ('x' * 70000,))
    elif kind == 'aggregate':
        kwargs = {'byte_limit': 100}
    elif kind == 'blob':
        change(native, 'UPDATE tasks SET body=?', (b'bad',))
    else:
        change(native, 'UPDATE tasks SET priority=?', (float('inf'),))
    with pytest.raises((ValueError, sqlite3.Error)):
        snap(native, **kwargs)


def test_A10_readonly_guards_adversarial(native, monkeypatch):
    from workshop_collectors.base import ReadTransaction
    real = ReadTransaction.rows
    tried = False
    def adversary(self, table):
        nonlocal tried
        if not tried:
            tried = True
            with pytest.raises(sqlite3.DatabaseError):
                self._db.execute("UPDATE tasks SET status='done'")
            # query_only alone is not the fence: mode=ro still prevents DML after it is turned off.
            self._db.execute('PRAGMA query_only=OFF')
            with pytest.raises(sqlite3.DatabaseError):
                self._db.execute("DELETE FROM task_events")
            self._db.execute('PRAGMA query_only=ON')
        return real(self, table)
    monkeypatch.setattr(ReadTransaction, 'rows', adversary)
    before = hashes(native)
    snap(native)
    assert tried and hashes(native) == before


@pytest.mark.parametrize('fingerprint', [None, 22, 'unverified', 'other:1|22', 'boot:1|23'])
def test_A05_pid_reuse_or_unverified_never_becomes_live(native, fingerprint):
    from workshop_collectors.hermes_work import ProcessSample
    change(native, 'UPDATE task_runs SET worker_started_at=?', (fingerprint,))
    s = snap(native, process_probe=lambda pid: ProcessSample(pid, 'boot:1|22', 'S'))
    assert s.inspect(1)['alive'] is not True
    assert s.execution(1)['progress'] == 'unknown'
    assert s.execution(1)['retry'] == 'not_requested'


def test_A05_silent_process_is_liveness_not_progress_or_tool_activity(native):
    from workshop_collectors.hermes_work import ProcessSample
    s = snap(native, process_probe=lambda pid: ProcessSample(pid, 'boot:1|22', 'S'))
    assert s.inspect(1)['alive'] is True
    assert s.inspect(1)['evidence_class'] == 'runtime_observed'
    e = s.execution(1)
    assert e['process'] == 'alive'
    assert e['progress'] == 'unknown'
    assert e['tool_activity'] == 'unsupported'
    assert e['failure'] == 'unknown'
    assert e['retry'] == 'not_requested'


@pytest.mark.parametrize('error', [PermissionError, FileNotFoundError, OSError])
def test_A05_probe_failure_unknown_not_failure(native, error):
    def probe(pid):
        raise error()
    s = snap(native, process_probe=probe)
    assert s.inspect(1)['alive'] is None
    assert s.execution(1)['failure'] == 'unknown'


def test_A05_no_probe_and_turn_finalization_do_not_prove_process_death(native):
    change(native, "UPDATE task_events SET kind='on_session_end'")
    s = snap(native)
    assert s.inspect(1)['alive'] is None
    assert s.execution(1)['attempt'] == 'running'
    assert s.execution(1)['process'] == 'unknown'


@pytest.mark.parametrize('station', ['blocked', 'review'])
def test_A06_attempt_exit_keeps_station_and_ack_never_accepts(native, station):
    from workshop.api import LocalAPI
    from workshop.contracts import AlarmRule
    from workshop.reducer import Reducer
    from workshop_collectors.hermes_work import ProcessSample
    change(native, 'UPDATE tasks SET status=?', (station,))
    change(native, "UPDATE task_runs SET status='done',ended_at=8,outcome='completed'")
    before = hashes(native)
    s = snap(native, process_probe=lambda pid: ProcessSample(pid, 'boot:1|22', 'S'))
    e = s.execution(1)
    assert e['attempt'] == 'exited'
    assert e['process'] == 'alive'  # disposition transition can precede actual process exit
    assert e['task_station'] == station
    r = Reducer()
    r.alarms.register(AlarmRule('loss', 'work', 'lost observation', 'unknown', 'inspect', 'soon',
                              'board', 'low', 'operator'))
    r.alarms.update('loss', True, now=10)
    api = LocalAPI(r)
    api.acknowledge(r.alarms.occurrences[0].id, now=11, authorized=True)
    assert r.alarms.occurrences[0].acknowledged
    assert snap(native).execution(1)['task_station'] == station
    assert hashes(native) == before


def test_A06_unknown_status_not_coerced_to_todo_or_accepted(native):
    change(native, "UPDATE tasks SET status='future_state'")
    s = snap(native)
    assert s.task_detail('task')['station'] == 'unknown'
    assert s.board_view()['columns']['unknown'][0]['status'] == 'future_state'


def test_A05_disconnect_preserves_last_observation_and_recovery(native):
    c = collector(native)
    first = c.observe(board='synthetic-board', acquired_at=10)
    native.rename(native.with_suffix('.offline'))
    with pytest.raises(sqlite3.Error):
        c.observe(board='synthetic-board', acquired_at=11)
    assert c.last_snapshot is first
    assert c.quality(now=12) == 'disconnected'
    native.with_suffix('.offline').rename(native)
    c.observe(board='synthetic-board', acquired_at=13)
    assert c.quality(now=14) == 'fresh'
    assert c.quality(now=30) == 'stale'
    assert c.quality(now=50) == 'disconnected'


def test_A05_actual_silent_subprocess_identity(native):
    from workshop_collectors.hermes_work import linux_process_probe
    # Test-owned silent child, no native agent signals or progress output.
    child = subprocess.Popen(['sleep', '30'])
    try:
        identity = linux_process_probe(child.pid)
        assert identity.fingerprint and identity.pid == child.pid
        change(native, 'UPDATE task_runs SET worker_pid=?, worker_started_at=?',
               (child.pid, identity.fingerprint))
        s = snap(native, process_probe=linux_process_probe)
        assert s.inspect(1)['alive'] is True
        assert s.execution(1)['progress'] == 'unknown'
        change(native, "UPDATE task_events SET kind='on_session_end'")
        assert snap(native, process_probe=linux_process_probe).inspect(1)['alive'] is True
    finally:
        child.terminate()
        child.wait(timeout=5)
    assert snap(native, process_probe=linux_process_probe).inspect(1)['alive'] is None
