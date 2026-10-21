#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Opt-in, one-shot evidence on the sole approved local Kanban store.

No daemon/listener, hooks or native helper imports. Prints only hashes, counts,
state labels and observation limits, never native body/payload/command text.
Fixture tests never call this script. Repeated acquisition is not a live watch.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'backend'), str(ROOT / 'collectors')]
from workshop_collectors.hermes_work import HermesWork, approved_scope, linux_process_probe


def fence(path):
    db = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, isolation_level=None, timeout=.1)
    try:
        db.execute('PRAGMA query_only=ON')
        schema = tuple(db.execute('SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name'))
    finally:
        db.close()
    with path.open('rb') as stream:
        byte_hash = hashlib.file_digest(stream, 'sha256').hexdigest()
    return {'main_sha256': byte_hash, 'schema_sha256': hashlib.sha256(repr(schema).encode()).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--approved-local', action='store_true', help='explicitly acquire the approved native board')
    args = parser.parse_args()
    if not args.approved_local:
        parser.error('native acquisition requires --approved-local; no implicit source discovery')
    scope = approved_scope()
    collector = HermesWork(scope, process_probe=linux_process_probe)
    checks = []
    last = None
    for surface in ('board_view', 'task_detail', 'workers', 'run', 'inspect'):
        before = fence(scope.path)
        snapshot = collector.observe(board=scope.board, acquired_at=time.monotonic())
        # Select a real observed ID; never manufacture fixture data for live evidence.
        if surface in ('board_view', 'workers'):
            getattr(snapshot, surface)()
        elif surface == 'task_detail':
            tasks = [t for rows in snapshot.board_view()['columns'].values() for t in rows]
            if not tasks:
                raise RuntimeError('No observed task for task-detail proof')
            snapshot.task_detail(tasks[0]['id'])
        else:
            runs = snapshot._tables['task_runs']
            if not runs:
                raise RuntimeError('No observed attempt for run/inspect proof')
            getattr(snapshot, surface)(runs[-1]['id'])
        after = fence(scope.path)
        checks.append({'surface': surface, 'before': before, 'after': after, 'unchanged': before == after})
        if before != after:
            raise RuntimeError('Native main/schema changed during observation; concurrent native writers/checkpoint must be investigated')
        last = snapshot
    runs = last._tables['task_runs']
    tasks = [t for rows in last.board_view()['columns'].values() for t in rows]
    executions = [last.execution(r['id']) for r in runs]
    report = {
        'scope': {'source_instance': scope.source_instance, 'board': scope.board, 'profiles': scope.profiles},
        'mapping_version': last.mapping_version, 'native_write_enabled': False,
        'surfaces': checks, 'latest_event_id': last.latest_event_id,
        'source_snapshot_complete': last.complete, 'truncated_tables': last.truncated_tables,
        'runtime_coverage': last.runtime_coverage,
        'observed_task_stations': dict(Counter(t['status'] for t in tasks)),
        'observed_attempt_statuses': dict(Counter(r['status'] for r in runs)),
        'observed_event_kinds': dict(Counter(e['kind'] for e in last._tables['task_events'])),
        'process_observations': dict(Counter(e['process'] for e in executions)),
        'attempt_task_stations': dict(Counter(e['task_station'] for e in executions)),
        'progress': 'unknown', 'tool_activity': 'unsupported', 'retry': 'not_requested',
        'limitations': [
            'Five independent snapshots; each snapshot has one read transaction plus a matching board-local event watermark.',
            'Process corroboration is sampled after the DB transaction, not atomic with that watermark.',
            'Native event cursor is not a global revision or a runtime inventory/replay guarantee.',
            'Main DB/schema invariant excludes WAL/SHM reader coordination; live native writers were not stopped.',
            'One-shot actual work observation, not continuous capture of every live station transition.',
            'Historical source records are not fresh runtime execution or tool-progress evidence.',
            'A05 silent tool, turn-finalisation and PID-reuse variants use isolated synthetic DBs plus a real test-owned silent child.',
            'A06 blocked/review exit and acknowledgement variants use synthetic native DBs; no live task was changed.',
            'No durable correlation/ingest, outbox, daemon, renderer or Phase-2/MVP acceptance in this slice.',
        ],
    }
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
