#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Approved local workflow -> bounded outbox -> OTLP -> historian -> projection.

Explicit opt-in only. Writes only this checkout's git-ignored Workshop state.
No daemon, native control, schedule access, listener or renderer. Run serially.
"""
import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'backend'), str(ROOT / 'collectors')]
from workshop.storage import Storage
from workshop_collectors.hermes_work import HermesWork, approved_scope, linux_process_probe
from workshop_collectors.hermes_runtime import HermesRuntime, runtime_binding, initial_state
from workshop_collectors.outbox import Outbox
from workshop_collectors.workflow import verify_agreement
from observe_work import fence
from observe_runtime import _deny_empty_scope


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--approved-local', action='store_true')
    args = parser.parse_args()
    if not args.approved_local:
        parser.error('native acquisition requires --approved-local; no implicit source discovery')
    scope = approved_scope()
    directory = ROOT / '.workshop-state'
    if directory.is_symlink():
        raise ValueError('Workshop state directory must not be a symlink')
    directory.mkdir(exist_ok=True)
    historian = directory / 'workflow-historian.db'
    outbox = directory / 'workflow-outbox.db'
    if any(p.is_symlink() for p in (historian, outbox)):
        raise ValueError('Workshop state files must not be symlinks')
    # The clock identity belongs to orchestration, not collector/domain code.
    clock_id = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    binding = runtime_binding(scope)
    observer = HermesRuntime(HermesWork(scope, process_probe=linux_process_probe), binding)
    before = fence(scope.path)
    q = Outbox(outbox, binding=binding, clock_id=clock_id)
    try:
        existed = historian.exists()
        store = Storage(historian) if existed else Storage(historian, initial=initial_state(binding, scope))
        try:
            startup = store.read()
            invalidated = all(e.acquired_at is None for e in startup.reducer.executions.values()
                              if e.lifecycle.mapped not in {'succeeded', 'failed', 'cancelled'})
            pending_before = q.status()['pending']
            while q.deliver_one(store, received_at=time.monotonic()) is not None:
                pass
            snapshot = observer.observe(board=scope.board, acquired_at=time.monotonic())
            if not snapshot.observations():
                raise RuntimeError('No current native attempts; historical inventory is not current proof')
            denial = _deny_empty_scope(observer, snapshot, scope, directory)
            sequence = q.enqueue(snapshot)
            delivered = q.deliver_one(store, received_at=time.monotonic())
            report = verify_agreement(observer, snapshot, store, now=time.monotonic())
            if not report['compared_attempts'] or q.status()['pending']:
                raise RuntimeError('Workflow was not completely delivered')
            after = fence(scope.path)
            if before != after:
                raise RuntimeError('Native main/schema changed; investigate concurrent writer/checkpoint and rerun')
            report.update(actual_live_observation=True,
                scope={'source_instance': scope.source_instance, 'board': scope.board, 'profiles': scope.profiles},
                native_fence={'before': before, 'after': after, 'unchanged': True},
                historian={'reopened': existed, 'startup_live_freshness_invalidated': invalidated,
                    'source_cursor': store.read().source_cursors['runtime'],
                    'reconcile_required': store.read().ingests['runtime'].reconcile_required},
                outbox={'delivered_cursor': sequence, 'observations_accepted': delivered.accepted,
                    'pending_before_acquisition': pending_before, **q.status()},
                task_scope_denial=denial,
                scenario_coverage={
                    'A05': 'actual acquired process/source agreement; silence/PID-reuse/turn variants isolated',
                    'A06': 'actual acquired station/attempt independence; forced blocked/review/ack variants isolated',
                    'A08': ('actual durable delivery/readback + reopened historian' if existed
                            else 'actual initial durable delivery/readback; reopen not yet exercised')
                            + '; crash/overflow/disconnect variants isolated',
                    'A10': 'actual same-data empty-scope denial + main/schema invariant; DML interlock attacks isolated',
                    'A25': 'one-shot observer exits; uninstall/restore + schedule invariants isolated, not shared live operations'},
                limitations=[
                    'Only this approved local board and profile scope, not fleet-wide health or MVP readiness.',
                    'Bounded source tables plus later proc observations have no atomic runtime watermark.',
                    'Partial native/event history never implies complete runtime coverage or deletion of unseen records.',
                    'Same-acquisition comparison, not continuous capture of all workflow transitions.',
                    'No live silent-tool/forced station transition/uninstall/schedule access was performed.',
                    'Main/schema hashes exclude WAL/SHM coordination; native writers were not stopped.',
                    'Outbox bounds logical pending payloads; historian/domain history and SQLite physical files are not byte-capped.',
                    'Comparable monotonic boot clock required; new boot/configuration needs explicit recovery, never timestamp rebasing.',
                    'Core independent review/merge is the Phase 2 acceptance gate; no renderer or running service.'])
            print(json.dumps(report, indent=2, sort_keys=True))
        finally:
            store.close()
    finally:
        q.close()


if __name__ == '__main__':
    main()
