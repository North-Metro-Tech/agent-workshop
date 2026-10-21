# SPDX-License-Identifier: Apache-2.0
"""Bounded read-only SQLite primitive, NOT a Hermes schema adapter/collector.

The path, exact table schema and equality filters are trusted local adapter
configuration. No arbitrary SQL or connection escapes. Returned rows are source
records, not runtime liveness, complete inventory or an atomic source watermark.
Only synthetic files are exercised in Phase 1; see docs/source-binding.md.
"""
from dataclasses import dataclass
import json
from pathlib import Path
import re
import sqlite3

from .ingest import MAX_BATCH, MAX_EVENT, MAX_REQUEST


@dataclass(frozen=True)
class ReadBatch:
    rows: tuple[dict, ...]
    truncated: bool


def _identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,127}', value):
        raise ValueError('Unsupported SQLite identifier')
    return '"' + value + '"'


def read_table(path, *, table, schema, where=None, limit=MAX_BATCH):
    """Read one short snapshot with exact ordered (name, declared type) checks.

    At most 256 rows / 1 MiB, 64 KiB per row; fetch one lookahead row to flag
    truncation. Read/schema/size/busy/VM-budget errors return no partial batch.
    A false truncated flag is NOT proof of full adapter/workflow coverage.
    Connections close on success and every failure; live WAL is never immutable.
    """
    quoted_table = _identifier(table)
    if (not isinstance(schema, tuple) or not schema or len(schema) > 64
            or any(not isinstance(c, tuple) or len(c) != 2 for c in schema)):
        raise ValueError('Expected explicit ordered SQLite schema')
    names = []
    for name, kind in schema:
        _identifier(name)
        if not isinstance(kind, str) or kind not in {'TEXT', 'INTEGER', 'REAL', 'BLOB', 'NUMERIC', ''}:
            raise ValueError('Unsupported declared SQLite type')
        names.append(name)
    if len(set(names)) != len(names):
        raise ValueError('Duplicate SQLite schema column')
    if type(limit) is not int or not 1 <= limit <= MAX_BATCH:
        raise ValueError('Read limit must be within 1..256')
    where = {} if where is None else where
    if not isinstance(where, dict) or not set(where) <= set(names):
        raise ValueError('Filter outside configured schema')
    for value in where.values():
        if type(value) not in (str, int, type(None)) or len(str(value).encode()) > MAX_EVENT:
            raise ValueError('Unsupported or oversized SQLite filter')
        if type(value) is int and not -(2**63) <= value < 2**63:
            raise ValueError('SQLite filter integer outside int64')
    sql = 'SELECT * FROM ' + quoted_table
    if where:
        sql += ' WHERE ' + ' AND '.join(_identifier(k) + ' IS ?' for k in where)
    sql += ' LIMIT ?'
    uri = Path(path).resolve().as_uri() + '?mode=ro'
    db = sqlite3.connect(uri, uri=True, timeout=0.1, isolation_level=None)
    try:
        db.execute('PRAGMA query_only=ON')
        db.execute('PRAGMA trusted_schema=OFF')
        db.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, MAX_EVENT)
        # Bound even a scan without an index; no read transaction waits on I/O
        # outside SQLite, a UI, or a callback supplied by the caller.
        budget = 100
        def progress():
            nonlocal budget
            budget -= 1
            return int(budget <= 0)
        db.set_progress_handler(progress, 1000)
        db.execute('BEGIN')
        entry = db.execute('SELECT type,sql FROM sqlite_master WHERE name=?', (table,)).fetchone()
        if (entry is None or entry[0] != 'table' or not entry[1]
                or not entry[1].lstrip().upper().startswith('CREATE TABLE')):
            raise ValueError('Expected an ordinary SQLite table')
        actual = tuple((c[1], c[2]) for c in db.execute('PRAGMA table_xinfo(' + quoted_table + ')'))
        if actual != schema:
            raise ValueError('Unsupported SQLite source schema')
        cursor = db.execute(sql, (*where.values(), limit + 1))
        safe, size, truncated = [], 0, False
        for row in cursor:
            if len(safe) == limit:
                truncated = True
                break
            value = dict(zip(names, row))
            try:
                encoded = json.dumps(value, ensure_ascii=False, allow_nan=False).encode('utf-8')
            except (ValueError, TypeError, UnicodeError) as exc:
                raise ValueError('Unsupported SQLite source record') from exc
            size += len(encoded)
            if len(encoded) > MAX_EVENT or size > MAX_REQUEST:
                raise ValueError('SQLite source batch exceeds byte bound')
            safe.append(value)
        db.execute('COMMIT')
        return ReadBatch(tuple(safe), truncated)
    except sqlite3.DataError as exc:
        raise ValueError('SQLite source record exceeds byte bound') from exc
    finally:
        db.close()
