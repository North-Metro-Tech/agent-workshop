# SPDX-License-Identifier: Apache-2.0
"""Adversarial A10 boundary assertions, all data synthetic."""
import json
import sqlite3

import pytest

from workshop.acquisition import read_table
from workshop.api import LocalAPI
from workshop.ingest import Acquisition
from test_source_scope import SCHEMA, configured, native


def test_A10_aggregate_bound_stops_cursor_before_materializing_whole_batch(native, monkeypatch):
    with sqlite3.connect(native) as db:
        db.execute('DELETE FROM tasks')
        db.executemany('INSERT INTO tasks VALUES (?,?,?)',
                       [(str(i), 'a', 'x' * 40000) for i in range(50)])
    from workshop import acquisition
    real = sqlite3.connect
    fetched = []
    closed = []
    class Cursor:
        def __init__(self, inner):
            self.inner = inner
        def fetchall(self):
            rows = self.inner.fetchall()
            fetched.extend(rows)
            return rows
        def __iter__(self):
            for row in self.inner:
                fetched.append(row)
                yield row
    class Connection(sqlite3.Connection):
        def execute(self, sql, *args):
            result = super().execute(sql, *args)
            return Cursor(result) if sql.startswith('SELECT *') else result
        def close(self):
            closed.append(True)
            super().close()
    def connect(database, **kw):
        return real(database, factory=Connection, **kw)
    monkeypatch.setattr(acquisition.sqlite3, 'connect', connect)
    before = native.read_bytes()
    with pytest.raises(ValueError, match='byte bound'):
        read_table(native, table='tasks', schema=SCHEMA)
    assert 1 < len(fetched) < 50
    assert closed == [True]
    assert native.read_bytes() == before


def test_A10_otlp_resource_and_identity_attributes_cannot_change_binding():
    state = configured()
    attrs = {'workshop.record.id': 'one', 'workshop.execution.id': 'same',
        'workshop.session.id': 'same', 'workshop.lifecycle': 'active',
        'gen_ai.agent.id': 'runtime-c', 'workshop.runtime': 'runtime-c',
        'workshop.role': 'c', 'source': 'urn:synthetic:c'}
    encode = lambda fields: [{'key': k, 'value': {'stringValue': v}} for k, v in fields.items()]
    payload = {'resourceLogs': [{'resource': {'attributes': encode({'service.instance.id': 'runtime-c'})},
        'scopeLogs': [{'logRecords': [{'attributes': encode(attrs)}]}]}]}
    assert state.ingests['a'].otlp('logs', json.dumps(payload).encode(),
                                  context=Acquisition(10, 10, 'boot')).accepted == 1
    projection = LocalAPI(state.reducer).snapshot(now=10)
    e = projection['executions'][0]
    assert e['key'] == {'runtime': 'runtime-a', 'native_id': 'same'}
    assert e['role'] == 'a'
    assert e['lifecycle']['source'] == 'urn:synthetic:a'
    assert state.reducer.roles['c'].present == set()


def test_A10_unknown_SQLite_extra_column_rejected_and_bytes_unchanged(native):
    with sqlite3.connect(native) as db:
        db.execute('ALTER TABLE tasks ADD COLUMN secret TEXT')
    before = native.read_bytes()
    with pytest.raises(ValueError, match='schema'):
        read_table(native, table='tasks', schema=SCHEMA)
    assert native.read_bytes() == before


@pytest.mark.parametrize('shape', ['oversized', 'blob', 'view'])
def test_A10_unsupported_SQLite_values_and_views_fail_closed(native, shape):
    with sqlite3.connect(native) as db:
        if shape == 'view':
            db.execute('CREATE VIEW projection AS SELECT * FROM tasks')
        else:
            db.execute('DELETE FROM tasks')
            db.execute('INSERT INTO tasks VALUES (?,?,?)',
                       ('1', 'a', 'x' * 70000 if shape == 'oversized' else b'raw bytes'))
    before = native.read_bytes()
    with pytest.raises(ValueError):
        read_table(native, table='projection' if shape == 'view' else 'tasks', schema=SCHEMA)
    assert native.read_bytes() == before
