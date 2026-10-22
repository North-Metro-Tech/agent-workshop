# SPDX-License-Identifier: Apache-2.0
"""Read-only Kanban observations, not native control or runtime inventory.

All five semantic views derive from one bounded SQLite read snapshot. Process
inspection is opt-in, outside the read transaction and never part of its atomic
watermark. No native plugins/helpers/hooks, psutil, cmdline, logs or attachments
are opened. Durable ingress/correlation belongs to the next Phase 2 slice.
"""
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
import re
import sqlite3

from workshop.contracts import FeedPolicy, timestamp
from workshop.freshness import quality
from .base import SCHEMAS, SourceScope, read_snapshot

APPROVED_PATH = Path('/home/aaron/.hermes/kanban/boards/agent-workshop/kanban.db')
MAPPING_VERSION = 'hermes-kanban-sqlite-v1'
STATIONS = ('triage', 'todo', 'ready', 'running', 'blocked', 'review', 'done', 'archived')
_PRIVATE = {'tasks': ('body', 'result', 'last_failure_error', 'skills'),
            'task_comments': ('body',), 'task_events': ('payload',),
            'task_runs': ('summary', 'metadata', 'error'),
            'task_attachments': ('stored_path',)}


def approved_scope(*, path=APPROVED_PATH, board='agent-workshop'):
    """The only approved live binding. No environment/current-board fallback."""
    if Path(path) != APPROVED_PATH or Path(path).resolve() != APPROVED_PATH or board != 'agent-workshop':
        raise ValueError('Source is outside approved local scope')
    return SourceScope('local-hermes-agent-workshop', board, APPROVED_PATH,
                       ('coder', 'default'))


@dataclass(frozen=True)
class ProcessSample:
    pid: int
    fingerprint: str
    state: str


def _proc_stat(pid):
    # Only fixed metadata files; never environ/cmdline/FD targets or process control.
    with Path('/proc', str(pid), 'stat').open() as stream:
        text = stream.read(4097)
    if len(text) > 4096:
        raise ValueError('Oversized proc stat')
    actual_pid = int(text.split(' ', 1)[0])
    tail = text.rsplit(')', 1)[1].split()
    return actual_pid, tail[0], tail[19]


def linux_process_probe(pid):
    """Minimal local Linux corroboration matching native spawn fingerprint.

    Two reads reject process replacement during sampling. Missing/denied proc
    metadata is unknown at the adapter boundary, never a fabricated terminal.
    """
    if type(pid) is not int or pid <= 0:
        raise ValueError('Invalid process PID')
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    if not re.fullmatch(r'[0-9a-f-]{36}', boot):
        raise ValueError('Unsupported boot identity')
    _, _, pid1_start = _proc_stat(1)
    actual, state, start = _proc_stat(pid)
    again, state2, start2 = _proc_stat(pid)
    if actual != pid or again != pid or start != start2:
        raise ValueError('Process incarnation changed during inspection')
    if not start.isdecimal() or not pid1_start.isdecimal():
        raise ValueError('Invalid process start identity')
    return ProcessSample(pid, f'{boot}:{pid1_start}|{start}', state2)


def _inspect(run, sample):
    result = {'run_id': run['id'], 'pid': run['worker_pid'], 'alive': None,
              'reason': 'no verified process observation', 'evidence_class': 'unknown'}
    recorded = run['worker_started_at']
    if not isinstance(recorded, str) or not re.fullmatch(r'[^|:]+:[0-9]+\|[0-9]+', recorded):
        result['reason'] = 'missing or unsupported spawn identity'
    elif sample is None:
        pass
    elif (not isinstance(sample, ProcessSample) or sample.pid != run['worker_pid']
          or not isinstance(sample.fingerprint, str)):
        result['reason'] = 'invalid process sample'
    elif sample.fingerprint != recorded:
        result['reason'] = 'process identity mismatch / PID reuse rejected'
    elif sample.state not in {'R', 'S', 'D', 'T', 't', 'I', 'Z', 'X', 'x', 'P', 'W'}:
        result['reason'] = 'unsupported process state'
    else:
        result.update(alive=sample.state not in {'Z', 'X', 'x'},
                      reason='matching spawn identity', evidence_class='runtime_observed',
                      process_state=sample.state)
    return result


class WorkSnapshot:
    def __init__(self, scope, tables, *, watermark, truncated, acquired_at, inspections):
        self.source_instance, self.board = scope.source_instance, scope.board
        self.latest_event_id = watermark
        self.truncated_tables = tuple(truncated)
        self.complete = not bool(truncated)
        self.acquired_at = acquired_at
        self.mapping_version = MAPPING_VERSION
        self.runtime_coverage = 'partial'
        self._tables = tables
        self._inspections = inspections

    def _provenance(self):
        return {'source_instance': self.source_instance, 'board': self.board,
                'acquired_at': self.acquired_at, 'mapping_version': self.mapping_version,
                'latest_event_id': self.latest_event_id, 'complete': self.complete,
                'runtime_coverage': self.runtime_coverage}

    def _row(self, table, key):
        for row in self._tables[table]:
            if row['id'] == key:
                return deepcopy(row)
        raise LookupError('Native record absent from bounded snapshot (not proof of deletion)')

    def board_view(self):
        columns = {name: [] for name in (*STATIONS, 'unknown')}
        for task in self._tables['tasks']:
            columns[task['status'] if task['status'] in STATIONS else 'unknown'].append(deepcopy(task))
        columns['done'].sort(key=lambda t: (t['completed_at'] is not None, t['completed_at'] or 0, t['id']), reverse=True)
        return {**self._provenance(), 'columns': columns,
                'diagnostics': 'unsupported (native runtime/config helpers intentionally not imported)',
                'evidence_class': 'source_record'}

    def task_detail(self, task_id):
        task = self._row('tasks', task_id)
        links = {'parents': [], 'children': []}
        for row in self._tables['task_links']:
            if row['child_id'] == task_id:
                links['parents'].append(row['parent_id'])
            if row['parent_id'] == task_id:
                links['children'].append(row['child_id'])
        return {**self._provenance(), 'task': task, 'station': task['status'] if task['status'] in STATIONS else 'unknown',
                'links': links, **{name: deepcopy([r for r in self._tables[table] if r['task_id'] == task_id])
                for name, table in (('comments', 'task_comments'), ('events', 'task_events'),
                                    ('attachments', 'task_attachments'), ('runs', 'task_runs'))},
                'complete': self.complete, 'evidence_class': 'source_record'}

    def workers(self):
        tasks = {t['id']: t for t in self._tables['tasks']}
        workers = [deepcopy(r) for r in self._tables['task_runs'] if r['ended_at'] is None
                   and r['worker_pid'] is not None and tasks.get(r['task_id'], {}).get('status') == 'running']
        workers.sort(key=lambda r: (r['started_at'], r['id']))
        return {**self._provenance(), 'workers': workers, 'count': len(workers),
                'evidence_class': 'source_record', 'liveness': 'not established by claimed rows'}

    def run(self, run_id):
        return {**self._provenance(), 'run': self._row('task_runs', run_id), 'evidence_class': 'source_record'}

    def inspect(self, run_id):
        self._row('task_runs', run_id)
        return {**self._provenance(), **deepcopy(self._inspections[run_id])}

    def execution(self, run_id):
        run = self._row('task_runs', run_id)
        try:
            task = self.task_detail(run['task_id'])
            station = task['station']
        except LookupError:
            station = 'unknown'
        observed = self.inspect(run_id)
        return {'key': (self.source_instance, self.board, str(run_id)),
                'task_key': (self.source_instance, self.board, run['task_id']),
                'attempt': 'exited' if run['ended_at'] is not None else
                           'running' if run['status'] == 'running' else 'unknown',
                'native_status': run['status'], 'native_outcome': run['outcome'],
                'task_station': station, 'disposition_evidence': 'source_record',
                'process': 'alive' if observed['alive'] is True else
                           'not_alive' if observed['alive'] is False else 'unknown',
                'progress': 'unknown', 'tool_activity': 'unsupported',
                'failure': 'unknown', 'retry': 'not_requested',
                'acquired_at': self.acquired_at, 'mapping_version': self.mapping_version}


class HermesWork:
    def __init__(self, scope, *, row_limit=256, byte_limit=1048576, process_probe=None):
        self.scope = scope
        self.row_limit, self.byte_limit, self.process_probe = row_limit, byte_limit, process_probe
        self.last_snapshot = None
        self._source_identity: tuple[int, int] | None = None
        self._disconnected = False

    def observe(self, *, board, acquired_at):
        if board != self.scope.board:
            raise ValueError('Requested board differs from trusted board binding')
        timestamp(acquired_at)
        if self.last_snapshot and acquired_at < self.last_snapshot.acquired_at:
            raise ValueError('Acquisition clock regressed')
        try:
            with read_snapshot(self.scope, row_limit=self.row_limit, byte_limit=self.byte_limit) as tx:
                if self._source_identity is not None and tx.source_identity != self._source_identity:
                    raise ValueError('Native source file identity changed; explicit rebind required')
                watermark = tx.watermark()
                tables = {table: tx.rows(table) for table in SCHEMAS}
                truncated = tuple(tx.truncated)
                if any(r['profile'] is not None and r['profile'] not in self.scope.profiles
                       for r in tables['task_runs']):
                    raise ValueError('Run profile outside approved source scope')
            # Process reads must not hold the native read transaction open. They
            # are corroboration at acquisition, not an atomic native DB field.
            inspections = {}
            for run in tables['task_runs']:
                sample = None
                if (self.process_probe is not None and type(run['worker_pid']) is int
                        and run['worker_pid'] > 0):
                    try:
                        sample = self.process_probe(run['worker_pid'])
                    except (OSError, ValueError, IndexError):
                        pass
                inspections[run['id']] = _inspect(run, sample)
            for table, fields in _PRIVATE.items():
                for row in tables[table]:
                    for field in fields:
                        row[field] = None
            result = WorkSnapshot(self.scope, tables, watermark=watermark, truncated=truncated,
                                  acquired_at=acquired_at, inspections=inspections)
        except (sqlite3.Error, ValueError, OSError):
            self._disconnected = True
            raise
        self.last_snapshot = result
        self._source_identity = tx.source_identity
        self._disconnected = False
        return result

    def quality(self, *, now):
        timestamp(now)
        if self.last_snapshot is None:
            return 'unknown'
        observed_quality = quality(self.last_snapshot.acquired_at, now, FeedPolicy(5, 15, 30))
        if self._disconnected and observed_quality != 'unknown':
            return 'disconnected'
        return observed_quality
