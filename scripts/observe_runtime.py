#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Opt-in one-shot approved board -> scoped ingest -> Workshop historian proof.

Writes ONLY the git-ignored .workshop-state/ under this checkout. No native
helpers, hooks, daemon, discovery, schedule reads, or agent controls. Existing
historian open is a service restart, not a passive read. Run serially.
"""
import argparse
from collections import Counter
from dataclasses import replace
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'backend'), str(ROOT / 'collectors')]
from workshop.storage import Storage
from workshop_collectors.hermes_work import HermesWork, approved_scope, linux_process_probe
from workshop_collectors.hermes_runtime import HermesRuntime, runtime_binding, initial_state
from observe_work import fence


def _deny_empty_scope(observer, snapshot, scope, directory):
    """Same actual bytes; deliberately denied policy; separate disposable historian."""
    denied_binding = replace(observer.binding, task_scopes=())
    denied_observer = HermesRuntime(observer.work, denied_binding)
    denied_snapshot = replace(snapshot, binding=denied_binding)
    with TemporaryDirectory(dir=directory, prefix='scope-denial-') as temp:
        store = Storage(Path(temp) / 'denied.db', initial=initial_state(denied_binding, scope))
        try:
            before = store.snapshot(now=snapshot.acquired_at)
            try:
                denied_observer.publish(store, 'runtime', denied_snapshot,
                    received_at=time.monotonic(), epoch='denied-proof', source_cursor=1)
            except ValueError as error:
                if 'scope' not in str(error):
                    raise
            else:
                raise RuntimeError('Empty task scope accepted actual source evidence')
            if store.snapshot(now=snapshot.acquired_at) != before:
                raise RuntimeError('Denied batch changed durable historian')
            saved = store.read()
            if saved.source_cursors or saved.source_identities or saved.reducer.executions:
                raise RuntimeError('Denied batch persisted source identity/cursor or execution')
        finally:
            store.close()
    return {'actual_source_data': True, 'empty_scope_denied': True, 'historian_unchanged': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--approved-local', action='store_true')
    args = parser.parse_args()
    if not args.approved_local:
        parser.error('native acquisition requires --approved-local; no implicit source discovery')
    scope = approved_scope()
    directory = ROOT / '.workshop-state'
    if directory.is_symlink():
        raise ValueError('Historian directory must not be a symlink')
    directory.mkdir(exist_ok=True)
    historian = directory / 'hermes-runtime.db'
    if historian.is_symlink():
        raise ValueError('Historian must not be a symlink')
    binding = runtime_binding(scope)
    observer = HermesRuntime(HermesWork(scope, process_probe=linux_process_probe), binding)
    before = fence(scope.path)
    snapshot = observer.observe(board=scope.board, acquired_at=time.monotonic())
    if not snapshot.observations():
        raise RuntimeError('No current native attempts acquired; retained history is not current proof')
    denial = _deny_empty_scope(observer, snapshot, scope, directory)
    existed = historian.exists()
    store = Storage(historian) if existed else Storage(historian, initial=initial_state(binding, scope))
    try:
        started = store.read()
        restart_invalidated = all(e.acquired_at is None for e in started.reducer.executions.values()
                                   if e.lifecycle.mapped not in {'succeeded', 'failed', 'cancelled'})
        source_cursor = started.source_cursors.get('runtime', 0) + 1
        result = observer.publish(store, 'runtime', snapshot, received_at=time.monotonic(),
                                  epoch=uuid.uuid4().hex, source_cursor=source_cursor)
        saved = store.read()
        view = store.snapshot(now=time.monotonic())
        if not saved.reducer.executions:
            raise RuntimeError('No actual native attempts acquired; no fixture substitution')
        if saved.source_cursors['runtime'] != source_cursor:
            raise RuntimeError('Historian cursor did not persist')
        if saved.ingests['runtime'].binding != binding:
            raise RuntimeError('Historian binding mismatch')
        if view['projection']['native_write_enabled']:
            raise RuntimeError('Native write interlock violated')
        if saved.reducer.roles[binding.role].complete:
            raise RuntimeError('Partial runtime coverage promoted to complete')
        after = fence(scope.path)
        if before != after:
            raise RuntimeError('Native main/schema changed; investigate concurrent native writers/checkpoint')
        records = snapshot.observations()
        report = {
            'actual_live_observation': True,
            'task_scope_denial': denial,
            'scope': {'source_instance': scope.source_instance, 'board': scope.board, 'profiles': scope.profiles},
            'native_fence': {'before': before, 'after': after, 'unchanged': before == after},
            'historian': {'reopened': existed, 'startup_live_freshness_invalidated': restart_invalidated,
                'correlated_attempts': len(saved.reducer.executions),
                'task_links': sum(e.task is not None for e in saved.reducer.executions.values()),
                'observations_accepted': result.accepted, 'source_cursor': source_cursor,
                'reconcile_required': saved.ingests['runtime'].reconcile_required,
                'binding_class': binding.evidence_class},
            'observed_processes': dict(Counter(r['process'] for r in records)),
            'observed_lifecycle': dict(Counter(r['lifecycle'] for r in records)),
            'observed_task_stations': dict(Counter(r['task_station'] for r in records)),
            'native_complete': snapshot.native_complete, 'native_event_cursor': snapshot.native_event_cursor,
            'atomic_runtime_watermark': snapshot.atomic_watermark,
            'runtime_coverage': snapshot.runtime_coverage, 'native_write_enabled': False,
            'role_availability': saved.reducer.summary(binding.role, now=time.monotonic())['availability'],
            'limitations': [
                'Actual approved Kanban attempts; native facts are source_record, not runtime lifecycle proof.',
                'Exact matching process incarnation only corroborates process liveness; no tool/session/progress inference.',
                'Native tables and later proc samples have no shared atomic runtime watermark; no complete recovery claim.',
                'Collector stream cursor is historian-owned monotonic input, NOT the diagnostic board event cursor.',
                'Main DB/schema invariant excludes WAL/SHM reader coordination; native writers were not stopped.',
                'One-shot observer naturally stops. Uninstall/schedule invariants use isolated deployment fixtures only.',
                'Restore re-establishes observation, never runtime availability from disk; ordinary events do not clear reconciliation.',
                'No renderer, outbox, daemon, hooks, schedule access, control, full Phase-2 or MVP acceptance.',
            ]}
        print(json.dumps(report, sort_keys=True, indent=2))
    finally:
        store.close()


if __name__ == '__main__':
    main()
