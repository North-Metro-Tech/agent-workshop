# SPDX-License-Identifier: Apache-2.0
"""A10 synthetic source scopes: no native environment or live integrations."""
from copy import deepcopy
from dataclasses import replace
import json
import sqlite3

import pytest

from workshop.api import LocalAPI
from workshop.contracts import ExecutionKey, FeedPolicy, TaskKey
from workshop.ingest import Acquisition, EVENT_TYPE, Ingest, SourceBinding
from workshop.reducer import Reducer
from workshop.storage import State, Storage


def configured():
    r = Reducer()
    ingests = {}
    for name in ('a', 'b', 'c'):
        r.register_role(name, scope=('chat',), inventory_approved=True)
        r.register_feed(name, FeedPolicy(5, 15, 30), group=name)
        instance, board = {'a': ('instance-a', 'board-a'),
                           'b': ('instance-a', 'board-b'),
                           'c': ('instance-b', 'board-a')}[name]
        ingests[name] = Ingest(r, SourceBinding('urn:synthetic:' + name,
            'runtime-' + name, name, name, task_scopes=((instance, board),)))
    return State(r, ingests)


def domain(name='a'):
    instance, board = {'a': ('instance-a', 'board-a'), 'b': ('instance-a', 'board-b'),
                       'c': ('instance-b', 'board-a')}[name]
    return dict(execution_id='same', session_id='same', lifecycle='active', revision=1,
                parent_execution_id='parent', task=dict(source_instance=instance,
                    namespace=board, native_id='1'))


def event(name='a', data=None):
    return dict(specversion='1.0', source='urn:synthetic:' + name, id='same',
                type=EVENT_TYPE, data=domain(name) if data is None else data)


def wire(value):
    return json.dumps(value).encode()


def test_A10_same_native_ids_have_distinct_instance_board_and_runtime_keys(tmp_path):
    s = Storage(tmp_path / 'synthetic-historian.db', initial=configured())
    for name in ('a', 'b', 'c'):
        assert s.cloudevents(name, wire(event(name)), context=Acquisition(10, 10, 'boot'),
                            source_cursor=1).accepted == 1
    r = s.read().reducer
    assert len(r.executions) == 3
    assert len({e.task for e in r.executions.values()}) == 3
    for name in ('a', 'b', 'c'):
        e = r.executions[ExecutionKey('runtime-' + name, 'same')]
        assert e.parent == ExecutionKey('runtime-' + name, 'parent')
        assert e.session == 'same'
        assert e.task == TaskKey(**domain(name)['task'])
        assert e.lifecycle.source == 'urn:synthetic:' + name
    path = s.path
    s.close()
    s = Storage(path)
    assert set(s.read().reducer.executions) == set(r.executions)
    assert s.read().ingests['a'].binding.task_scopes == (('instance-a', 'board-a'),)
    s.close()


@pytest.mark.parametrize('transport', ['ce', 'otlp', 'snapshot'])
@pytest.mark.parametrize('attack', ['instance', 'board', 'both'])
def test_A10_scope_spoof_rejected_atomically(tmp_path, transport, attack):
    s = Storage(tmp_path / 'synthetic-historian.db', initial=configured())
    before = s.snapshot(now=10)
    data = domain()
    if attack in ('instance', 'both'):
        data['task']['source_instance'] = 'instance-b'
    if attack in ('board', 'both'):
        data['task']['namespace'] = 'board-b'
    with pytest.raises(ValueError, match='scope'):
        if transport == 'ce':
            s.cloudevents('a', wire([event(), event(data=data)]),
                         context=Acquisition(10, 10, 'boot'), source_cursor=1)
        elif transport == 'otlp':
            attrs = {'workshop.execution.id': 'same', 'workshop.session.id': 'same',
                     'workshop.lifecycle': 'active', 'workshop.record.id': 'same',
                     **{'workshop.task.' + k: v for k, v in data['task'].items()}}
            payload = {'resourceLogs': [{'scopeLogs': [{'logRecords': [{'attributes': [
                {'key': k, 'value': {'stringValue': v}} for k, v in attrs.items()]}]}]}]}
            s.otlp('a', 'logs', wire(payload), context=Acquisition(10, 10, 'boot'), source_cursor=1)
        else:
            token = s.begin_snapshot('a', generation=1, scope=('chat',), epoch='boot',
                                     watermark=1, acquired_at=10, pages=('one',), complete=True)
            s.snapshot_page(token, 'one', [data])
    assert s.snapshot(now=10) == before
    assert s.read().ingests['a']._seen == {}
    assert s.read().source_cursors == {}
    s.close()


def test_A10_no_task_permission_by_default():
    state = configured()
    ingest = Ingest(state.reducer, replace(state.ingests['a'].binding, task_scopes=()))
    with pytest.raises(ValueError, match='scope'):
        ingest.cloudevents(wire(event()), context=Acquisition(10, 10, 'boot'))


@pytest.mark.parametrize('scopes', [[], ('instance', 'board'), (('instance',),),
    (('instance', 'board'), ('instance', 'board')), (('', 'board'),), ((1, 'board'),)])
def test_A10_invalid_trusted_scope_configuration_fails_closed(scopes):
    with pytest.raises(ValueError):
        SourceBinding('urn:synthetic:a', 'runtime-a', 'a', 'a', task_scopes=scopes)


def test_A10_cloudevents_source_cannot_select_another_binding():
    state = configured()
    before = LocalAPI(state.reducer).snapshot(now=10)
    with pytest.raises(ValueError, match='scope'):
        state.ingests['a'].cloudevents(wire(event('b')), context=Acquisition(10, 10, 'boot'))
    assert LocalAPI(state.reducer).snapshot(now=10) == before


def test_A10_durable_runtime_instance_collision_is_rejected(tmp_path):
    state = configured()
    state.ingests['b'].binding = replace(state.ingests['b'].binding, runtime='runtime-a')
    with pytest.raises(ValueError, match='runtime'):
        Storage(tmp_path / 'synthetic-bad-config.db', initial=state)


SCHEMA = (('id', 'TEXT'), ('board', 'TEXT'), ('disposition', 'TEXT'))


@pytest.fixture
def native(tmp_path):
    path = tmp_path / 'synthetic native?#%.db'
    db = sqlite3.connect(path)
    db.execute('CREATE TABLE tasks(id TEXT, board TEXT, disposition TEXT)')
    db.executemany('INSERT INTO tasks VALUES (?,?,?)', [('1', 'a', 'blocked'),
                      ('1', 'b', 'review'), ('2', 'a', 'ready')])
    db.execute('PRAGMA user_version=42')
    db.commit()
    db.close()
    return path


def test_A10_sqlite_bounded_scoped_acquisition_leaves_bytes_schema_and_records_unchanged(native):
    from workshop.acquisition import read_table
    before = native.read_bytes()
    listing = set(native.parent.iterdir())
    result = read_table(native, table='tasks', schema=SCHEMA, where={'board': 'a'}, limit=1)
    assert result.rows == ({'id': '1', 'board': 'a', 'disposition': 'blocked'},)
    assert result.truncated is True
    assert read_table(native, table='tasks', schema=SCHEMA, where={'board': 'b'}).rows == (
        {'id': '1', 'board': 'b', 'disposition': 'review'},)
    assert native.read_bytes() == before
    assert set(native.parent.iterdir()) == listing
    with sqlite3.connect(native) as db:
        assert db.execute('PRAGMA user_version').fetchone() == (42,)
        assert db.execute('SELECT * FROM tasks').fetchall() == [
            ('1', 'a', 'blocked'), ('1', 'b', 'review'), ('2', 'a', 'ready')]


def test_A10_sqlite_ro_and_query_only_are_enforced(native, monkeypatch):
    from workshop import acquisition
    real = sqlite3.connect
    calls = []
    class Guard(sqlite3.Connection):
        def execute(self, sql, *args):
            calls.append(sql)
            if sql.startswith('SELECT *'):
                assert super().execute('PRAGMA query_only').fetchone() == (1,)
                for statement in ("UPDATE tasks SET disposition='done'",
                                  'CREATE TABLE injected(id TEXT)', 'DROP TABLE tasks'):
                    with pytest.raises(sqlite3.OperationalError):
                        super().execute(statement)
                # Independently prove mode=ro, not just query_only, denies DML.
                super().execute('PRAGMA query_only=OFF')
                with pytest.raises(sqlite3.OperationalError):
                    super().execute("UPDATE tasks SET disposition='done'")
                super().execute('PRAGMA query_only=ON')
            return super().execute(sql, *args)
    def connect(database, **kw):
        assert database.endswith('?mode=ro') and kw['uri'] is True
        return real(database, factory=Guard, **kw)
    monkeypatch.setattr(acquisition.sqlite3, 'connect', connect)
    acquisition.read_table(native, table='tasks', schema=SCHEMA)
    assert 'BEGIN' in calls
    assert any(sql.startswith('SELECT *') for sql in calls)


@pytest.mark.parametrize('change', [dict(table='tasks; DROP TABLE tasks'),
    dict(schema=(('id', 'INTEGER'),)), dict(where={'missing': 'a'}), dict(limit=0),
    dict(limit=257), dict(limit=True)])
def test_A10_sqlite_rejects_unknown_schema_or_unbounded_query_unchanged(native, change):
    from workshop.acquisition import read_table
    before = native.read_bytes()
    with pytest.raises(ValueError):
        read_table(native, **(dict(table='tasks', schema=SCHEMA) | change))
    assert native.read_bytes() == before


def test_A10_sqlite_does_not_create_missing_source(tmp_path):
    from workshop.acquisition import read_table
    path = tmp_path / 'absent.db'
    with pytest.raises(sqlite3.OperationalError):
        read_table(path, table='tasks', schema=SCHEMA)
    assert not path.exists()


def test_A10_sqlite_live_WAL_is_visible_without_immutable(native):
    from workshop.acquisition import read_table
    with sqlite3.connect(native) as writer:
        writer.execute('PRAGMA journal_mode=WAL')
        writer.execute("INSERT INTO tasks VALUES ('3','a','review')")
        writer.commit()
        before = native.read_bytes(), native.with_name(native.name + '-wal').read_bytes()
        result = read_table(native, table='tasks', schema=SCHEMA, where={'id': '3'})
        assert result.rows[0]['disposition'] == 'review'
        assert before == (native.read_bytes(), native.with_name(native.name + '-wal').read_bytes())
