# SPDX-License-Identifier: Apache-2.0
"""Workshop-owned WAL historian and bounded, function-level recovery.

One service writer, serial calls, local filesystem only. Never point this at a
native actor database. Source cursors are trusted adapter sequence numbers,
NOT execution revisions, receipt times, or producer-supplied CE extensions.
No clock reads, listener, native acquisition, executor or package dependency.
"""
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass, field, fields, is_dataclass
import json
from pathlib import Path
import sqlite3
from typing import Any
import uuid

from .alarms import Controls, Occurrence
from .api import LocalAPI
from .contracts import (AlarmRule, Ambiguity, Execution, ExecutionKey, FeedPolicy,
                        Observation, TaskKey, timestamp)
from .freshness import Feed
from .ingest import (Acquisition, Ingest, SourceBinding, MAX_BATCH,
                     MAX_EVENT, MAX_REQUEST, MAPPING_VERSION, _canonical, _text)
from .reducer import LIFECYCLE, TERMINAL, Reducer, Role


@dataclass
class State:
    reducer: Reducer
    ingests: dict[str, Ingest] = field(default_factory=dict)
    source_cursors: dict[str, int] = field(default_factory=dict)
    generations: dict[str, int] = field(default_factory=dict)


class RecoveryRequired(ValueError):
    """Obtain a new atomic snapshot; do not retry an expired replay cursor."""


_TYPES: dict[str, Any] = {c.__name__: c for c in (Controls, Occurrence, AlarmRule, Ambiguity,
          Execution, ExecutionKey, FeedPolicy, Observation, TaskKey, Feed, Role,
          Acquisition, SourceBinding)}
_TABLES = ('roles', 'feeds', 'executions', 'correlations', 'ambiguities',
           'alarm_rules', 'alarm_controls', 'alarm_occurrences', 'alarm_audit', 'ingests')
APPLICATION_ID = 1096239921


def _encode(value: Any) -> Any:
    # Closed, data-only codec. Never pickle, import a named class, or eval a DB.
    if value is None or type(value) in (str, bool, int):
        return value
    if type(value) is float:
        return timestamp(value)
    if is_dataclass(value) and type(value).__name__ in _TYPES:
        return {'type': type(value).__name__, 'fields':
                {f.name: _encode(getattr(value, f.name)) for f in fields(value)}}
    if type(value) is dict:
        return {'type': 'dict', 'items': [[_encode(k), _encode(v)] for k, v in value.items()]}
    if type(value) in (list, tuple, set):
        items = [_encode(v) for v in value]
        if type(value) is set:
            items.sort(key=_json)
        return {'type': type(value).__name__, 'items': items}
    raise ValueError('Unsupported historian value')


def _decode(value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    kind = value['type']
    if kind in _TYPES:
        return _TYPES[kind](**{k: _decode(v) for k, v in value['fields'].items()})
    items = value['items']
    if kind == 'dict':
        return {_decode(k): _decode(v) for k, v in items}
    if kind in {'list', 'tuple', 'set'}:
        return {'list': list, 'tuple': tuple, 'set': set}[kind](_decode(v) for v in items)
    raise ValueError('Unknown historian type')


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':'))


def _pack(value: Any) -> str:
    return _json(_encode(value))


def _unpack(value: str) -> Any:
    return _decode(json.loads(value))


def _sections(state: State) -> dict[str, Any]:
    r, a = state.reducer, state.reducer.alarms
    data = {name: getattr(r, name) for name in ('roles', 'feeds', 'executions', 'correlations')}
    data['ambiguities'] = dict(enumerate(r.ambiguities))
    data.update(alarm_rules=a.rules, alarm_controls=a.controls,
                alarm_occurrences=dict(enumerate(a.occurrences)),
                alarm_audit=dict(enumerate(a.audit)))
    data['ingests'] = {name: {'binding': i.binding, 'state':
        {k: v for k, v in i.__dict__.items() if k not in {'reducer', 'binding', '_last_batch', '_last_effects'}}}
        for name, i in state.ingests.items()}
    data['internal'] = {'feed_alarms': r._feed_alarms, 'pending': a._pending,
        'incident': a._incident, 'last_update': a._last_update,
        'current': {k: o.id for k, o in a._current.items()},
        'source_cursors': state.source_cursors, 'generations': state.generations}
    return data


def _restore(data: dict[str, Any]) -> State:
    r = Reducer()
    for name in ('roles', 'feeds', 'executions', 'correlations'):
        setattr(r, name, data[name])
    r.ambiguities = [v for _, v in sorted(data['ambiguities'].items())]
    a = r.alarms
    a.rules, a.controls = data['alarm_rules'], data['alarm_controls']
    a.occurrences = [v for _, v in sorted(data['alarm_occurrences'].items())]
    a.audit = [v for _, v in sorted(data['alarm_audit'].items())]
    internal = data['internal']
    r._feed_alarms = internal['feed_alarms']
    a._pending, a._incident, a._last_update = (internal[k] for k in ('pending', 'incident', 'last_update'))
    by_id = {o.id: o for o in a.occurrences}
    for occurrence in a.occurrences:
        occurrence.controls = a.controls[occurrence.rule.name]
    a._current = {k: by_id[v] for k, v in internal['current'].items()}
    ingests = {}
    for name, entry in data['ingests'].items():
        i = Ingest(r, entry['binding'])
        i.__dict__.update(entry['state'])
        ingests[name] = i
    return State(r, ingests, internal['source_cursors'], internal['generations'])


def _number(value, label, minimum=0):
    if type(value) is not int or value < minimum or value >= 2**63:
        raise ValueError('Invalid ' + label)
    return value


def _invalidate(state):
    r = state.reducer
    for feed in r.feeds.values():
        feed.last_acquired_at = None
    for e in r.executions.values():
        if e.lifecycle.mapped not in TERMINAL:
            e.acquired_at = None
    for role in r.roles.values():
        role.complete = False
        role.reconciled_at = None
        role.signals = {k: (o, None) for k, (o, _) in role.signals.items()}
    for ingest in state.ingests.values():
        ingest.reconcile_required = True
        ingest._diagnose('service_restart')


class Storage:
    def __init__(self, path, *, initial=None, retention=128):
        _number(retention, 'retention', 2)
        self.path = Path(path)
        self.retention = retention
        self._active = False
        self._db = sqlite3.connect(self.path, isolation_level=None)
        try:
            db = self._db
            # Validate ownership BEFORE changing WAL mode, schema, or records.
            tables = {v[0] for v in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            version = db.execute('PRAGMA user_version').fetchone()[0]
            app = db.execute('PRAGMA application_id').fetchone()[0]
            if tables and (app != APPLICATION_ID or version != 1):
                raise ValueError('Not a supported Workshop-owned database')
            if not tables and (initial is None or version != 0 or app != 0):
                raise ValueError('New historian requires explicit initial State')
            if initial is not None:
                self._validate(initial)
                _pack(_sections(initial))
            if db.execute('PRAGMA journal_mode=WAL').fetchone()[0] != 'wal':
                raise ValueError('Historian requires a local WAL-capable file')
            db.execute('PRAGMA synchronous=FULL')
            db.execute('PRAGMA busy_timeout=5000')
            if not tables:
                db.executescript(Path(__file__).with_name('migrations').joinpath('001_initial.sql').read_text())
                with self._atomic():
                    self._set_meta('identity', uuid.uuid4().hex)
                    self._set_meta('revision', 0)
                    self._save(deepcopy(initial), {'kind': 'initial'})
            else:
                with self._atomic():
                    state = self._load()
                    _invalidate(state)
                    db.execute('DELETE FROM snapshot_jobs')
                    self._save(state, {'kind': 'restart'})
        except BaseException:
            self._db.close()
            raise

    @staticmethod
    def _validate(state):
        if not isinstance(state, State):
            raise ValueError('Historian requires State')
        bindings = [i.binding for i in state.ingests.values()]
        # A complete-role inventory must have one configured reconciliation owner.
        for attribute in ('source', 'feed', 'role'):
            if len({getattr(b, attribute) for b in bindings}) != len(bindings):
                raise ValueError('Storage requires dedicated source, role and feed bindings')
        for name, i in state.ingests.items():
            _text(name, 'ingest name')
            if i.reducer is not state.reducer:
                raise ValueError('Ingress must share the stored reducer')

    def close(self):
        self._db.close()

    @contextmanager
    def _atomic(self, *, read=False):
        if self._active:
            raise RuntimeError('Nested/concurrent Storage calls are not supported')
        self._active = True
        try:
            self._db.execute('BEGIN' if read else 'BEGIN IMMEDIATE')
            try:
                yield
                self._db.execute('COMMIT')
            except BaseException:
                self._db.execute('ROLLBACK')
                raise
        finally:
            self._active = False

    def _meta(self, name):
        return _unpack(self._db.execute('SELECT payload FROM metadata WHERE id=?', (name,)).fetchone()[0])

    def _set_meta(self, name, value):
        self._db.execute('INSERT OR REPLACE INTO metadata VALUES (?,?)', (name, _pack(value)))

    def _load(self):
        data = {table: {_unpack(k): _unpack(v) for k, v in
            self._db.execute(f'SELECT id,payload FROM {table}')} for table in _TABLES}
        data['internal'] = self._meta('internal')
        return _restore(data)

    def _save(self, state, event):
        self._validate(state)
        sections = _sections(state)
        encoded = _pack(sections)  # fail serialization before any DELETE
        for table in _TABLES:
            self._db.execute(f'DELETE FROM {table}')
            self._db.executemany(f'INSERT INTO {table} VALUES (?,?)',
                [(_pack(k), _pack(v)) for k, v in sections[table].items()])
        self._set_meta('internal', sections['internal'])
        revision = self._meta('revision') + 1
        self._set_meta('revision', revision)
        self._db.execute('INSERT INTO revisions VALUES (?,?,?)', (revision, encoded, _pack(event)))
        self._db.execute('DELETE FROM revisions WHERE revision <= ?', (revision - self.retention,))

    def read(self):
        with self._atomic(read=True):
            return self._load()

    @contextmanager
    def transaction(self):
        """Stage trusted Workshop-local changes; nothing is published on failure.

        Do not perform network I/O/waits inside this short writer transaction.
        Native observations go through the ingress methods, not this escape hatch.
        """
        with self._atomic():
            state = self._load()
            yield state
            self._save(state, {'kind': 'local'})

    def _cursor(self, revision):
        return f'{self._meta("identity")}:{revision}'

    def _revision(self, cursor):
        try:
            identity, sequence = cursor.split(':')
            if identity != self._meta('identity') or not sequence.isascii() or not sequence.isdigit():
                raise ValueError()
            revision = _number(int(sequence), 'cursor')
            current = self._meta('revision')
            oldest = self._db.execute('SELECT MIN(revision) FROM revisions').fetchone()[0]
            if revision > current or revision < oldest - 1:
                raise ValueError()
            return revision
        except (AttributeError, TypeError, ValueError) as exc:
            raise RecoveryRequired('Cursor invalid/expired; obtain an atomic snapshot') from exc

    def snapshot(self, *, now):
        timestamp(now)
        with self._atomic(read=True):
            state = self._load()
            return {'cursor': self._cursor(self._meta('revision')),
                    'projection': LocalAPI(state.reducer).snapshot(now=now)}

    def replay(self, cursor, *, now):
        timestamp(now)
        with self._atomic(read=True):
            revision = self._revision(cursor)
            return [{'cursor': self._cursor(seq), 'projection':
                     LocalAPI(_restore(_unpack(data)).reducer).snapshot(now=now)}
                    for seq, data in self._db.execute(
                        'SELECT revision,state FROM revisions WHERE revision>? ORDER BY revision', (revision,))]

    def _ingest(self, name, method, args, context, source_cursor):
        _number(source_cursor, 'source cursor')
        with self._atomic():
            state = self._load()
            previous = state.source_cursors.get(name, 0)
            if source_cursor < previous:
                raise RecoveryRequired('Source cursor regressed; reacquire snapshot')
            ingest = state.ingests[name]
            result = getattr(ingest, method)(*args, context=context)
            records, ctx = ingest._last_batch
            if source_cursor == previous and (result.accepted or result.corroborated or result.ignored):
                raise ValueError('Source cursor reused for new observations')
            state.source_cursors[name] = source_cursor
            applied = []
            for index in ingest._last_effects:
                native = ExecutionKey(ingest.binding.runtime, records[index]['domain']['execution_id'])
                applied.append(state.reducer.correlations.get(native, (native, ''))[0])
            self._save(state, {'kind': 'ingest', 'source': name, 'source_cursor': source_cursor,
                               'records': records, 'context': ctx, 'applied': applied})
            return result

    def cloudevents(self, name, payload, *, context, source_cursor):
        return self._ingest(name, 'cloudevents', (payload,), context, source_cursor)

    def otlp(self, name, signal, payload, *, context, source_cursor):
        return self._ingest(name, 'otlp', (signal, payload), context, source_cursor)

    def begin_snapshot(self, name, *, generation, scope, epoch, watermark,
                       acquired_at, pages, complete):
        _number(generation, 'snapshot generation', 1)
        _number(watermark, 'source watermark')
        timestamp(acquired_at)
        _text(epoch, 'snapshot epoch')
        if (type(complete) is not bool or not isinstance(pages, tuple) or not pages
                or len(pages) > 64 or len(set(pages)) != len(pages)):
            raise ValueError('Invalid page manifest/completeness')
        for page in pages:
            _text(page, 'page identity')
        with self._atomic():
            state = self._load()
            ingest = state.ingests[name]
            role = state.reducer.roles[ingest.binding.role]
            if (not isinstance(scope, tuple) or not scope or len(set(scope)) != len(scope)
                    or not set(scope) <= set(role.scope)):
                raise ValueError('Snapshot outside configured scope')
            pending = self._db.execute('SELECT payload FROM snapshot_jobs WHERE source=?', (name,)).fetchone()
            high = state.generations.get(name, 0)
            if pending:
                high = max(high, _unpack(pending[0])['generation'])
            if generation <= high:
                raise ValueError('Snapshot generation must increase')
            if watermark < state.source_cursors.get(name, 0):
                raise ValueError('Snapshot watermark regressed')
            if epoch in ingest._retired_epochs or ingest._epoch not in (None, epoch):
                raise RecoveryRequired('Snapshot epoch requires matching source acquisition')
            token = uuid.uuid4().hex
            job = dict(source=name, generation=generation, scope=scope, epoch=epoch,
                       watermark=watermark, acquired_at=acquired_at, manifest=pages,
                       complete=complete, pages={}, revision=self._meta('revision'))
            self._db.execute('INSERT OR REPLACE INTO snapshot_jobs VALUES (?,?,?)', (name, token, _pack(job)))
            return token

    def _job(self, token):
        row = self._db.execute('SELECT payload FROM snapshot_jobs WHERE token=?', (token,)).fetchone()
        if row is None:
            raise RecoveryRequired('Snapshot token retired; reacquire snapshot')
        return _unpack(row[0])

    def snapshot_page(self, token, page, records):
        if not isinstance(records, list) or len(records) > MAX_BATCH:
            raise ValueError('Snapshot page exceeds record bound')
        if len(_canonical(records)) > MAX_REQUEST:
            raise ValueError('Snapshot page exceeds byte bound')
        with self._atomic():
            job = self._job(token)
            if page not in job['manifest']:
                raise ValueError('Page outside declared manifest')
            ingest = self._load().ingests[job['source']]
            safe = []
            for record in records:
                if len(_canonical(record)) > MAX_EVENT:
                    raise ValueError('Snapshot domain record exceeds byte bound')
                safe.append(ingest._domain(record))
            if len({r['execution_id'] for r in safe}) != len(safe):
                raise ValueError('Duplicate execution in snapshot page')
            if page in job['pages'] and job['pages'][page] != safe:
                raise ValueError('Changed snapshot page identity')
            other_ids = {r['execution_id'] for p, rows in job['pages'].items() if p != page for r in rows}
            if other_ids.intersection(r['execution_id'] for r in safe):
                raise ValueError('Duplicate execution across snapshot pages')
            job['pages'][page] = safe
            self._db.execute('UPDATE snapshot_jobs SET payload=? WHERE token=?', (_pack(job), token))

    def finish_snapshot(self, token):
        with self._atomic():
            job = self._job(token)
            if set(job['pages']) != set(job['manifest']):
                raise RecoveryRequired('Missing snapshot pages; no replacement committed')
            self._revision(self._cursor(job['revision']))
            state = self._load()
            name = job['source']
            current = state.ingests[name]
            if current._epoch not in (None, job['epoch']):
                raise RecoveryRequired('Epoch changed during snapshot; reacquire')
            events = [_unpack(v[0]) for v in self._db.execute(
                'SELECT event FROM revisions WHERE revision>? ORDER BY revision', (job['revision'],))]
            if any(e['kind'] != 'ingest' for e in events):
                raise RecoveryRequired('Local state changed during snapshot; reacquire')
            r = state.reducer
            b = current.binding
            role = r.roles[b.role]
            records = [record for page in job['manifest'] for record in job['pages'][page]]
            usable = (job['complete'] and set(job['scope']) == set(role.scope)
                      and b.evidence_class == 'runtime_observed'
                      and all(record['lifecycle'] in LIFECYCLE for record in records))
            # Replay membership/ordering from the pre-snapshot service cursor.
            # Current state ALREADY contains the reduced journal events. Protect
            # their newer fields rather than rolling back history and applying
            # them twice (which could lose terminal/conflicting observations).
            newer = {key for event in events
                     if event['source'] != name or event['source_cursor'] > job['watermark']
                     for key in event['applied']}
            old_present = set(role.present)
            keys = set()
            at = job['acquired_at'] if usable else None
            for record in records:
                key = ExecutionKey(b.runtime, record['execution_id'])
                canonical = r.correlations.get(key, (key, ''))[0]
                keys.add(canonical)
                native = record['lifecycle']
                parent = record.get('parent_execution_id')
                task = record.get('task')
                parent_key = ExecutionKey(b.runtime, parent) if parent else None
                task_key = TaskKey(**task) if task else None
                observation = Observation(native, native if native in LIFECYCLE else 'unknown',
                    MAPPING_VERSION, b.source, b.feed, None, native in LIFECYCLE, b.evidence_class)
                if canonical in newer:
                    previous = r.executions[canonical]
                    identity_changed = (b.role, record['session_id'], parent_key, task_key) != (
                        previous.role, previous.session, previous.parent, previous.task)
                    authority_conflict = (b.source != previous.lifecycle.source
                                          and observation.mapped != previous.lifecycle.mapped)
                    if identity_changed or authority_conflict:
                        # This path MUST run the reducer's discrepancy checks,
                        # not suppress a role conflict behind newer-key protection.
                        r.observe_execution(b.role, key, session=record['session_id'],
                            parent=parent_key, task=task_key, lifecycle=observation,
                            acquired_at=None)
                    else:
                        previous.observations.append(observation)
                    continue
                old_revision = current._ordering.get(canonical, (None, None))[0]
                revision = record.get('revision')
                if old_revision is not None and revision is not None and revision < old_revision:
                    raise RecoveryRequired('Snapshot execution revision regressed; reacquire')
                r.observe_execution(b.role, key, session=record['session_id'],
                    parent=parent_key, task=task_key, lifecycle=observation,
                    acquired_at=at, source_ordered=True)
                current._ordering[canonical] = (revision, at)
            if usable:
                role.present = keys | (old_present & newer)
                for key in old_present - role.present:
                    execution = r.executions[key]
                    if execution.lifecycle.mapped not in TERMINAL:
                        execution.acquired_at = None
            else:
                role.present.update(old_present | keys)
            # History and disputed sets are append-preserving. Absence can
            # replace complete inventory, never fabricate a terminal lifecycle.
            role.complete = usable
            role.claimed_scope = job['scope']
            role.reconciled_at = job['acquired_at']
            role.reconcile_feed = b.feed
            feed = r.feeds[b.feed]
            if usable:
                assert at is not None
                if feed.last_acquired_at is None or at >= feed.last_acquired_at:
                    feed.acquire(at)
            current._epoch = job['epoch']
            current.reconcile_required = not usable
            if not usable:
                current._diagnose('partial_snapshot')
            state.generations[name] = job['generation']
            if usable:
                state.source_cursors[name] = max(job['watermark'], state.source_cursors.get(name, 0))
            self._save(state, {'kind': 'snapshot', 'source': name,
                'generation': job['generation'], 'watermark': job['watermark'],
                'scope': job['scope'], 'epoch': job['epoch'],
                'acquired_at': job['acquired_at'], 'complete': usable})
            self._db.execute('DELETE FROM snapshot_jobs WHERE token=?', (token,))
