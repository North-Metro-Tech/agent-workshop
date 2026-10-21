# SPDX-License-Identifier: Apache-2.0
"""Deterministic synthetic collector demo. No live acquisition or clock reads.

Creates only temporary fixture files, using the production collector/outbox/OTLP
path. All process samples are synthetic; output explicitly labels that coverage.
"""
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory

from workshop.storage import Storage
from .base import SCHEMAS, SourceScope
from .hermes_work import HermesWork, ProcessSample
from .hermes_runtime import HermesRuntime, runtime_binding, initial_state
from .outbox import Outbox
from .workflow import verify_agreement


def snapshot():
    with TemporaryDirectory(prefix='workshop-collector-demo-') as directory:
        root = Path(directory).resolve()
        native = root / 'synthetic.db'
        db = sqlite3.connect(native)
        try:
            for table, columns in SCHEMAS.items():
                db.execute('CREATE TABLE ' + table + ' (' + ','.join(n + ' ' + t for n, t in columns) + ')')
            for number, station in enumerate(('running', 'blocked', 'review'), start=1):
                db.execute('INSERT INTO tasks (id,assignee,status,created_at,current_run_id) VALUES (?,?,?,?,?)',
                           ('task-' + str(number), 'coder', station, number, number))
                db.execute('INSERT INTO task_runs (id,task_id,profile,status,worker_pid,worker_started_at,'
                           'started_at,ended_at,outcome) VALUES (?,?,?,?,?,?,?,?,?)',
                           (number, 'task-' + str(number), 'coder', 'running' if number == 1 else 'done',
                            100 + number, 'synthetic:1|22', 2, None if number == 1 else 8,
                            None if number == 1 else 'completed'))
            db.execute("INSERT INTO task_events (id,task_id,kind,created_at) VALUES (1,'task-1','spawned',2)")
            db.commit()
        finally:
            db.close()
        scope = SourceScope('synthetic-instance', 'synthetic-board', native, ('coder', 'vitruvius-core'))
        binding = runtime_binding(scope)
        observer = HermesRuntime(HermesWork(scope,
            process_probe=lambda pid: ProcessSample(pid, 'synthetic:1|22', 'S')), binding)
        queue = Outbox(root / 'outbox.db', binding=binding, clock_id='synthetic-clock')
        store = Storage(root / 'historian.db', initial=initial_state(binding, scope))
        try:
            acquired = observer.observe(board=scope.board, acquired_at=10)
            sequence = queue.enqueue(acquired)
            delivered = queue.deliver_one(store, received_at=100)
            report = verify_agreement(observer, acquired, store, now=100)
            # Omit opaque generated stream identity, never replace it with a
            # fabricated value. All remaining fixture evidence is deterministic.
            report['acquisition_evidence'].pop('epoch')
            report.update(synthetic_only=True, actual_live_observation=False,
                process_samples='synthetic, not OS processes',
                delivered_cursor=sequence, observations_accepted=delivered.accepted,
                pending=queue.status()['pending'],
                original_acquired_at=10, received_at=100,
                feed_quality_at_delivery=store.read().reducer.feed_quality(binding.feed, now=100),
                limitations=['Synthetic fixture DB and process samples only; never live evidence.',
                             'Partial runtime coverage; queued receipt does not refresh original acquisition.',
                             'No global health, renderer, service, native controls or MVP-readiness claim.'])
            return report
        finally:
            queue.close()
            store.close()


def main():
    print(json.dumps(snapshot(), sort_keys=True, indent=2))


if __name__ == '__main__':
    main()
