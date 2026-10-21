# SPDX-License-Identifier: Apache-2.0
"""Explicit trusted local scopes and bounded, short read-only SQLite snapshots.

No native helpers, SQL/callback supplied by telemetry, migrations, checkpoints,
network, wall clocks or write-capable connections. WAL coordination may occur.
"""
from contextlib import contextmanager
from dataclasses import dataclass
import json
from pathlib import Path
import sqlite3


# Installed adapter revision, NOT inferred from a new/unrecognised source.
_SCHEMA_TEXT = {
    'tasks': 'id:T title:T body:T assignee:T status:T priority:I created_by:T created_at:I started_at:I completed_at:I workspace_kind:T workspace_path:T branch_name:T project_id:T claim_lock:T claim_expires:I tenant:T result:T idempotency_key:T consecutive_failures:I worker_pid:I worker_started_at:I last_failure_error:T max_runtime_seconds:I last_heartbeat_at:I current_run_id:I workflow_template_id:T current_step_key:T skills:T model_override:T provider_override:T reasoning_effort:T max_retries:I goal_mode:I goal_max_turns:I session_id:T block_kind:T block_recurrences:I completion_contract:T',
    'task_runs': 'id:I task_id:T profile:T step_key:T status:T claim_lock:T claim_expires:I worker_pid:I worker_started_at:I max_runtime_seconds:I last_heartbeat_at:I started_at:I ended_at:I outcome:T summary:T metadata:T error:T',
    'task_events': 'id:I task_id:T run_id:I kind:T payload:T created_at:I',
    'task_comments': 'id:I task_id:T author:T body:T created_at:I',
    'task_attachments': 'id:I task_id:T filename:T stored_path:T content_type:T size:I uploaded_by:T created_at:I',
    'task_links': 'parent_id:T child_id:T',
}
SCHEMAS = {table: tuple((name, {'T': 'TEXT', 'I': 'INTEGER'}[kind])
                      for name, kind in (col.split(':') for col in columns.split()))
           for table, columns in _SCHEMA_TEXT.items()}


@dataclass(frozen=True)
class SourceScope:
    """Trusted local exact DB/instance/board binding, never producer input.

    Construction itself does not authorise a new source. Deployments must use
    the reviewed approved_scope() factory; generic construction exists for
    isolated fixtures and future separately-approved adapters.
    """
    source_instance: str
    board: str
    path: Path
    profiles: tuple[str, ...]

    def __post_init__(self):
        if not all(isinstance(v, str) and v.strip() for v in (self.source_instance, self.board)):
            raise ValueError('Explicit source instance and board required')
        if (not isinstance(self.profiles, tuple) or not self.profiles
                or len(set(self.profiles)) != len(self.profiles)
                or not all(isinstance(p, str) and p.strip() for p in self.profiles)):
            raise ValueError('Explicit profile scope required')
        path = Path(self.path)
        if not path.is_absolute() or path != path.resolve():
            raise ValueError('Exact absolute nonsymlink source path required')
        object.__setattr__(self, 'path', path)


class ReadTransaction:
    """Internal capability; must not escape read_snapshot's short context."""
    def __init__(self, db, *, row_limit, byte_limit):
        self._db = db
        self.row_limit, self.byte_limit = row_limit, byte_limit
        self.bytes_read = 0
        self.truncated = []

    def validate(self):
        for table, schema in SCHEMAS.items():
            entry = self._db.execute('SELECT type,sql FROM sqlite_master WHERE name=?', (table,)).fetchone()
            if (entry is None or entry[0] != 'table' or not entry[1]
                    or not entry[1].lstrip().upper().startswith('CREATE TABLE')):
                raise ValueError('Expected ordinary SQLite table: ' + table)
            columns = tuple(self._db.execute('PRAGMA table_xinfo("' + table + '")'))
            if (tuple((c[1], c[2]) for c in columns) != schema or any(c[6] for c in columns)):
                raise ValueError('Unsupported exact source schema: ' + table)

    def watermark(self):
        value = self._db.execute('SELECT COALESCE(MAX(id),0) FROM task_events').fetchone()[0]
        if type(value) is not int or value < 0:
            raise ValueError('Invalid native event watermark')
        return value

    def rows(self, table):
        if table not in SCHEMAS:
            raise ValueError('Unconfigured source table')
        order = ('priority DESC,created_at ASC,id ASC' if table == 'tasks'
                 else 'parent_id,child_id' if table == 'task_links' else 'id ASC')
        cursor = self._db.execute('SELECT * FROM "' + table + '" ORDER BY ' + order + ' LIMIT ?',
                                  (self.row_limit + 1,))
        rows = []
        for raw in cursor:
            if len(rows) == self.row_limit:
                self.truncated.append(table)
                break
            row = dict(zip((c[0] for c in SCHEMAS[table]), raw))
            try:
                size = len(json.dumps(row, ensure_ascii=False, allow_nan=False).encode('utf-8'))
            except (ValueError, TypeError, UnicodeError) as exc:
                raise ValueError('Unsupported source record') from exc
            self.bytes_read += size
            if size > 65536 or self.bytes_read > self.byte_limit:
                raise ValueError('Source snapshot exceeds byte bound')
            rows.append(row)
        return tuple(rows)


@contextmanager
def read_snapshot(scope, *, row_limit=256, byte_limit=1048576):
    if type(row_limit) is not int or not 1 <= row_limit <= 256:
        raise ValueError('Row bound must be within 1..256 per table')
    if type(byte_limit) is not int or not 1 <= byte_limit <= 1048576:
        raise ValueError('Aggregate byte bound must be within 1..1048576')
    if scope.path != scope.path.resolve():
        raise ValueError('Source path binding changed')
    db = sqlite3.connect(scope.path.as_uri() + '?mode=ro', uri=True, timeout=.1, isolation_level=None)
    try:
        db.execute('PRAGMA query_only=ON')
        db.execute('PRAGMA trusted_schema=OFF')
        db.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, 65536)
        budget = 500
        def progress():
            nonlocal budget
            budget -= 1
            return int(budget <= 0)
        db.set_progress_handler(progress, 1000)
        db.execute('BEGIN DEFERRED')
        tx = ReadTransaction(db, row_limit=row_limit, byte_limit=byte_limit)
        tx.validate()
        yield tx
        db.execute('COMMIT')
    except sqlite3.DataError as exc:
        raise ValueError('Source record exceeds byte bound') from exc
    finally:
        db.close()
