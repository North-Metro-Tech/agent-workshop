# SPDX-License-Identifier: Apache-2.0
"""Bounded Workshop-owned observation outbox, one serial local writer.

Only scoped RuntimeSnapshot data, never native SQL or task/agent control. FIFO
at-least-once delivery uses the existing bounded OTLP ingest. A crash between
historian commit and queue acknowledgement replays the exact record identity.
No clock reads: caller supplies comparable acquisition/receipt times and a stable
clock-domain identity (e.g. host boot ID for monotonic timestamps).
"""
from contextlib import contextmanager
from dataclasses import asdict
import json
from pathlib import Path
import sqlite3
import uuid

from workshop.contracts import timestamp
from workshop.ingest import Acquisition, MAX_REQUEST, SourceBinding, _text
from workshop.storage import RecoveryRequired
from .hermes_runtime import RuntimeSnapshot

APPLICATION_ID = 1096239922
_SCHEMA = {
    'meta': (('id', 'INTEGER'), ('value', 'TEXT')),
    'pending': (('cursor', 'INTEGER'), ('acquired', 'REAL'), ('payload', 'BLOB')),
}


def _json(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':'))


def _bound(value, maximum, name):
    if type(value) is not int or not 1 <= value <= maximum:
        raise ValueError('Invalid outbox ' + name)


def _observation_id(epoch, cursor, acquired, execution):
    # Bind immutable queue identity to ORIGINAL acquisition even when restart
    # reconciliation suppresses effective freshness in retained ingest metadata.
    return _json(['outbox-v1', epoch, cursor, acquired, execution])


def _payload(snapshot, epoch, cursor):
    wire = json.loads(snapshot._payload(epoch, cursor))
    for resource in wire['resourceLogs']:
        for scope in resource['scopeLogs']:
            for record in scope['logRecords']:
                attrs = {a['key']: a['value'] for a in record['attributes']}
                attrs['workshop.record.id']['stringValue'] = _observation_id(
                    epoch, cursor, snapshot.acquired_at, attrs['workshop.execution.id']['stringValue'])
    return _json(wire).encode()


class OutboxFull(BufferError):
    """Backpressure: nothing dropped, no cursor consumed; caller must report loss
    of any observation it elects not to retry. Capacity is not a replay guarantee.
    """


class Outbox:
    def __init__(self, path, *, binding, clock_id, max_items=64, max_bytes=4194304):
        _bound(max_items, 64, 'item bound')
        _bound(max_bytes, 4194304, 'byte bound')
        _text(clock_id, 'clock identity')
        if not isinstance(binding, SourceBinding) or binding.evidence_class != 'source_record':
            raise ValueError('Explicit source_record binding required')
        # Configuration is trusted local policy, not a telemetry-selected path.
        path = Path(path)
        if not path.is_absolute() or path != path.resolve():
            raise ValueError('Exact absolute nonsymlink outbox path required')
        self.binding = binding
        self.path = path
        self.config = {'binding': asdict(binding), 'clock_id': clock_id,
                       'max_items': max_items, 'max_bytes': max_bytes}
        self.config = json.loads(_json(self.config))
        if len(_json(self.config).encode()) > 65536:
            raise ValueError('Oversized outbox configuration')
        db = self._db = sqlite3.connect(path, isolation_level=None, timeout=.1)
        try:
            db.execute('PRAGMA trusted_schema=OFF')
            db.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, MAX_REQUEST + 65536)
            tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            app = db.execute('PRAGMA application_id').fetchone()[0]
            version = db.execute('PRAGMA user_version').fetchone()[0]
            if tables:
                if app != APPLICATION_ID or version != 1 or tables != set(_SCHEMA):
                    raise ValueError('Not a supported Workshop outbox')
                if db.execute("SELECT 1 FROM sqlite_master WHERE type IN ('trigger','view') LIMIT 1").fetchone():
                    raise ValueError('Unsupported outbox schema')
                for table, schema in _SCHEMA.items():
                    columns = tuple(db.execute('PRAGMA table_xinfo(' + table + ')'))
                    if tuple((r[1], r[2]) for r in columns) != schema or any(r[6] for r in columns):
                        raise ValueError('Unsupported outbox schema')
                meta = self._meta()
                if meta['config'] != self.config:
                    raise ValueError('Outbox configuration changed; explicit recovery required')
                self._usage()
            elif app != 0 or version != 0:
                raise ValueError('Not a supported Workshop outbox')
            # Validate ownership/configuration BEFORE journal or data mutations.
            if db.execute('PRAGMA journal_mode=WAL').fetchone()[0] != 'wal':
                raise ValueError('Outbox requires local WAL storage')
            db.execute('PRAGMA synchronous=FULL')
            if not tables:
                with self._atomic():
                    db.execute('CREATE TABLE meta (id INTEGER PRIMARY KEY CHECK(id=1), value TEXT NOT NULL)')
                    db.execute('CREATE TABLE pending (cursor INTEGER PRIMARY KEY, acquired REAL NOT NULL, payload BLOB NOT NULL)')
                    db.execute('PRAGMA application_id=' + str(APPLICATION_ID))
                    db.execute('PRAGMA user_version=1')
                    self._save({'config': self.config, 'epoch': uuid.uuid4().hex, 'next_cursor': 1,
                                'last_acquired': None, 'source_identity': None})
        except BaseException:
            db.close()
            raise

    @contextmanager
    def _atomic(self):
        self._db.execute('BEGIN IMMEDIATE')
        try:
            yield
            self._db.execute('COMMIT')
        except BaseException:
            self._db.execute('ROLLBACK')
            raise

    def _meta(self):
        rows = self._db.execute('SELECT value FROM meta LIMIT 2').fetchall()
        if len(rows) != 1 or not isinstance(rows[0][0], str) or len(rows[0][0].encode()) > 65536:
            raise ValueError('Invalid outbox metadata')
        meta = json.loads(rows[0][0])
        _bound(meta['next_cursor'], 2**63 - 1, 'cursor')
        _text(meta['epoch'], 'outbox epoch')
        if meta['last_acquired'] is not None:
            timestamp(meta['last_acquired'])
        identity = meta['source_identity']
        if identity is not None and (not isinstance(identity, list) or len(identity) != 2
                or any(type(n) is not int or n < 0 for n in identity)):
            raise ValueError('Invalid outbox source identity')
        return meta

    def _save(self, meta):
        self._db.execute('INSERT OR REPLACE INTO meta VALUES (1,?)', (_json(meta),))

    def _usage(self):
        count, size, largest = self._db.execute(
            'SELECT COUNT(*),COALESCE(SUM(length(payload)),0),COALESCE(MAX(length(payload)),0) FROM pending').fetchone()
        if (count > self.config['max_items'] or size > self.config['max_bytes'] or largest > MAX_REQUEST):
            raise ValueError('Stored outbox exceeds configured bounds')
        return count, size

    def status(self):
        """Counts only. Bytes bound retained payloads, NOT SQLite/WAL physical size."""
        meta = self._meta()
        count, size = self._usage()
        return {'pending': count, 'payload_bytes': size, 'next_cursor': meta['next_cursor'],
                'epoch': meta['epoch'], 'runtime_coverage': 'partial', 'overflow_policy': 'reject-no-drop'}

    def enqueue(self, snapshot):
        """Persist stable sequence/epoch plus original acquisition atomically.

        Full queues reject without mutation; never evict or manufacture complete
        recovery. RuntimeSnapshot is trusted adapter output, not producer input.
        """
        if not isinstance(snapshot, RuntimeSnapshot) or snapshot.binding != self.binding:
            raise ValueError('Snapshot binding mismatch')
        timestamp(snapshot.acquired_at)
        if not snapshot.observations():
            raise ValueError('Cannot enqueue empty observation snapshot')
        identity = snapshot.source_identity
        if (not isinstance(identity, tuple) or len(identity) != 2
                or any(type(n) is not int or n < 0 for n in identity)):
            raise ValueError('Invalid source identity')
        with self._atomic():
            meta = self._meta()
            cursor = meta['next_cursor']
            if cursor == 2**63 - 1:
                raise RecoveryRequired('Outbox cursor exhausted')
            if meta['last_acquired'] is not None and snapshot.acquired_at < meta['last_acquired']:
                raise ValueError('Acquisition clock regressed')
            if meta['source_identity'] is not None and list(identity) != meta['source_identity']:
                raise ValueError('Source identity changed; explicit rebind required')
            payload = _payload(snapshot, meta['epoch'], cursor)
            count, size = self._usage()
            if (len(payload) > MAX_REQUEST or count >= self.config['max_items']
                    or size + len(payload) > self.config['max_bytes']):
                raise OutboxFull('Observation outbox full; acquisition not queued (no drop/rebase)')
            self._db.execute('INSERT INTO pending VALUES (?,?,?)', (cursor, snapshot.acquired_at, payload))
            meta.update(next_cursor=cursor + 1, last_acquired=snapshot.acquired_at,
                        source_identity=list(identity))
            self._save(meta)
            return cursor

    def deliver_one(self, storage, *, received_at, name='runtime'):
        """FIFO delivery. Failure keeps head queued; commit-before-ack is retry-safe.

        Call serially with one historian writer. Never infer acquisition freshness
        from delivery. A clock-domain change requires explicit operator recovery,
        not relabelling old monotonic timestamps. No automatic cursor rebasing.
        """
        timestamp(received_at)
        state = storage.read()
        if name not in state.ingests or state.ingests[name].binding != self.binding:
            raise ValueError('Historian binding mismatch')
        self._usage()
        row = self._db.execute('SELECT cursor,acquired,payload FROM pending ORDER BY cursor LIMIT 1').fetchone()
        if row is None:
            return None
        cursor, acquired, payload = row
        if received_at < acquired:
            raise ValueError('Receipt precedes snapshot acquisition')
        previous = state.source_cursors.get(name, 0)
        if previous not in (cursor - 1, cursor):
            raise RecoveryRequired('Historian/outbox cursor divergence; explicit recovery required')
        meta = self._meta()
        ingest = state.ingests[name]
        if (meta['epoch'] in ingest._retired_epochs
                or (previous > 0 and ingest._epoch != meta['epoch'])):
            raise RecoveryRequired('Historian/outbox epoch divergence; explicit recovery required')
        result = storage.otlp(name, 'logs', payload,
            context=Acquisition(acquired, received_at, meta['epoch']), source_cursor=cursor,
            source_identity=tuple(meta['source_identity']))
        self._ack(cursor)
        return result

    def _ack(self, cursor):
        with self._atomic():
            if self._db.execute('DELETE FROM pending WHERE cursor=?', (cursor,)).rowcount != 1:
                raise RecoveryRequired('Outbox acknowledgement missing')

    def close(self):
        self._db.close()
