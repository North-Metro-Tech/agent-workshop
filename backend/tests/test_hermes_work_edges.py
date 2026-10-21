# SPDX-License-Identifier: Apache-2.0
"""Adversarial review additions for the work observer's trust/freshness fences."""
import ast
import inspect
from pathlib import Path
import sqlite3

import pytest

from test_hermes_work import native, change, collector, hashes, snap


def test_acquisition_clock_future_is_unknown(native):
    c = collector(native)
    c.observe(board='synthetic-board', acquired_at=10)
    assert c.quality(now=9) == 'unknown'
    with pytest.raises(ValueError, match='regressed'):
        c.observe(board='synthetic-board', acquired_at=9)
    assert c.last_snapshot.acquired_at == 10


def test_replaced_same_path_is_not_same_source_instance(native, tmp_path):
    c = collector(native)
    c.observe(board='synthetic-board', acquired_at=10)
    old = native.with_suffix('.original')
    native.rename(old)
    native.write_bytes(old.read_bytes())
    with pytest.raises(ValueError, match='identity'):
        c.observe(board='synthetic-board', acquired_at=11)
    assert c.last_snapshot.acquired_at == 10


def test_unknown_profile_fails_closed_no_last_refresh(native):
    c = collector(native)
    c.observe(board='synthetic-board', acquired_at=10)
    change(native, "UPDATE task_runs SET profile='unapproved'")
    with pytest.raises(ValueError, match='profile'):
        c.observe(board='synthetic-board', acquired_at=11)
    assert c.last_snapshot.acquired_at == 10
    assert c.quality(now=12) == 'disconnected'


def test_source_schema_hidden_column_rejected(native):
    change(native, 'ALTER TABLE tasks ADD COLUMN hidden INTEGER GENERATED ALWAYS AS (1) VIRTUAL')
    with pytest.raises(ValueError, match='schema'):
        snap(native)


@pytest.mark.parametrize('error', ['schema', 'oversize', 'success'])
def test_connections_close_and_never_omit_ro_uri(native, monkeypatch, error):
    from workshop_collectors import base
    real = sqlite3.connect
    connections = []
    def connect(database, **kwargs):
        assert database == native.as_uri() + '?mode=ro'
        assert kwargs['uri'] is True
        connection = real(database, **kwargs)
        connections.append(connection)
        return connection
    if error == 'schema':
        change(native, 'ALTER TABLE tasks ADD COLUMN bad TEXT')
    elif error == 'oversize':
        change(native, 'UPDATE tasks SET body=?', ('x' * 70000,))
    monkeypatch.setattr(base.sqlite3, 'connect', connect)
    if error == 'success':
        snap(native)
    else:
        with pytest.raises((ValueError, sqlite3.Error)):
            snap(native)
    assert len(connections) == 1
    with pytest.raises(sqlite3.ProgrammingError, match='closed'):
        connections[0].execute('SELECT 1')


def test_vm_scan_budget_bounded(native):
    # No source index: ORDER BY must scan; VM budget bounds work before a small output limit.
    db = sqlite3.connect(native)
    db.executemany('INSERT INTO tasks (id,priority,created_at) VALUES (?,0,1)',
                   ((str(i),) for i in range(100000)))
    db.commit()
    db.close()
    with pytest.raises(sqlite3.OperationalError, match='interrupted'):
        snap(native, row_limit=1)


def test_partial_tasks_do_not_discard_attempt_or_guess_station(native):
    change(native, "INSERT INTO task_runs (id,task_id,profile,status,started_at) VALUES (2,'unseen','coder','running',2)")
    s = snap(native)
    assert s.execution(2)['task_station'] == 'unknown'
    assert s.execution(2)['process'] == 'unknown'
    assert s.runtime_coverage == 'partial'


def test_task_id_injection_is_data_not_sql(native):
    s = snap(native)
    before = hashes(native)
    with pytest.raises(LookupError):
        s.task_detail("task'; DROP TABLE tasks; --")
    assert hashes(native) == before


def test_collector_structural_no_control_native_helpers_network_or_clock():
    from workshop_collectors.hermes_work import HermesWork, WorkSnapshot
    assert {n for n, f in inspect.getmembers(HermesWork, inspect.isfunction) if not n.startswith('_')} == {'observe', 'quality'}
    assert {n for n, f in inspect.getmembers(WorkSnapshot, inspect.isfunction) if not n.startswith('_')} == {'board_view', 'task_detail', 'workers', 'run', 'inspect', 'execution'}
    root = Path(__file__).parents[2] / 'collectors' / 'workshop_collectors'
    allowed = {'contextlib', 'dataclasses', 'json', 'pathlib', 'sqlite3', 'copy', 're',
               'workshop.contracts', 'workshop.freshness'}
    for path in root.glob('*.py'):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Import):
                assert all(alias.name in allowed for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and not node.level:
                assert node.module in allowed
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in {'eval', 'exec', '__import__'}


def test_approved_scope_ignores_board_and_db_environment(native, monkeypatch):
    from workshop_collectors.hermes_work import approved_scope, APPROVED_PATH
    monkeypatch.setenv('HERMES_KANBAN_BOARD', 'other')
    monkeypatch.setenv('HERMES_KANBAN_DB', str(native))
    scope = approved_scope()
    assert scope.path == APPROVED_PATH
    assert scope.board == 'agent-workshop'
