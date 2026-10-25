# SPDX-License-Identifier: Apache-2.0
"""Same-acquisition source/projection agreement, never a fleet health claim."""
from workshop.contracts import ExecutionKey, TaskKey
from workshop.reducer import ACTIVE
from .outbox import _observation_id


_NATIVE_STATUS = {'running', 'done', 'blocked', 'failed', 'unknown'}
_NATIVE_OUTCOME = {'completed', 'failed', 'cancelled', 'blocked', 'needs_input', 'interrupted', 'timed_out', 'unknown'}


def verify_agreement(observer, snapshot, storage, *, now):
    """Verify acquired native attempts against both durable facts and API output.

    This is a bounded same-acquisition comparison, NOT continuous event capture.
    The native table copy is already redacted by HermesWork. No source requery or
    process resampling (which could race the acquisition) occurs here.
    """
    work = observer.work.last_snapshot
    if work is None or work.acquired_at != snapshot.acquired_at:
        raise ValueError('Matching work acquisition required')
    saved = storage.read()
    projection = storage.snapshot(now=now)['projection']
    projected = {e['key']['native_id']: e for e in projection['executions']
                 if e['key']['runtime'] == observer.binding.runtime}
    records = {r['execution_id']: r for r in snapshot.observations()}
    ingest = saved.ingests['runtime']
    retained = {r['attributes']['workshop.execution.id']: r for r in ingest.records}
    if not records or len(records) != len(work._tables['task_runs']):
        raise ValueError('Nonempty matching acquisition required')
    cursor = saved.source_cursors.get('runtime')
    comparisons = []
    for run in work._tables['task_runs']:
        identity = str(run['id'])
        evidence = work.execution(run['id'])
        # Intentionally independent of the adapter's _lifecycle mapping.
        expected = 'unknown'
        if run['ended_at'] is None and run['status'] == 'running':
            expected = 'active'
        elif run['ended_at'] is not None and run['status'] == 'done':
            expected = {'completed': 'succeeded', 'failed': 'failed',
                        'cancelled': 'cancelled'}.get(run['outcome'], 'unknown')
        record = records[identity]
        fact = saved.reducer.executions[ExecutionKey(observer.binding.runtime, identity)]
        view = projected[identity]
        attrs = retained[identity]['attributes']
        if (attrs.get('workshop.record.id') != _observation_id(
                ingest._epoch, cursor, snapshot.acquired_at, identity)
                or retained[identity]['epoch'] != ingest._epoch
                or attrs.get('workshop.hermes.board.event_id') != work.latest_event_id
                or attrs.get('workshop.hermes.native.complete') != work.complete):
            raise ValueError('Current acquisition not durably delivered for attempt ' + identity)
        status = run['status'] if run['status'] in _NATIVE_STATUS else 'unknown'
        outcome = run['outcome'] if run['outcome'] in _NATIVE_OUTCOME else 'unknown'
        task = TaskKey(work.source_instance, work.board, run['task_id'])
        current = fact.lifecycle.mapped == expected and view['lifecycle']['mapped'] == expected
        # Reopen deliberately invalidates acquisition and retains earlier active
        # facts when an unsupported native lifecycle cannot prove a newer fact.
        # This is presentation agreement, NOT current canonical lifecycle proof.
        retained_prior = (expected == 'unknown' and not current
            and ingest.reconcile_required is True
            and fact.lifecycle.mapped in ACTIVE and fact.lifecycle.supported is True
            and fact.lifecycle.evidence_class == 'source_record'
            and fact.acquired_at is None
            and view['lifecycle']['mapped'] == fact.lifecycle.mapped
            and view['lifecycle']['supported'] is True
            and view['lifecycle_quality'] == 'unknown')
        checks = [fact.task == task, current or retained_prior,
            fact.lifecycle.evidence_class == 'source_record', record['lifecycle'] == expected,
            view['lifecycle']['evidence_class'] == 'source_record',
            view['task'] == {'source_instance': task.source_instance,
                            'namespace': task.namespace, 'native_id': task.native_id},
            attrs['workshop.hermes.process'] == evidence['process'] == record['process'],
            attrs['workshop.hermes.task.station'] == evidence['task_station'] == record['task_station'],
            attrs['workshop.hermes.attempt.status'] == record['attempt_status'] == status,
            attrs['workshop.hermes.attempt.outcome'] == record['attempt_outcome'] == outcome,
            evidence['progress'] == 'unknown', evidence['tool_activity'] == 'unsupported',
            evidence['retry'] == 'not_requested', evidence['failure'] == 'unknown']
        if not all(checks):
            raise ValueError('Source/projection disagreement for attempt ' + identity)
        comparisons.append({'execution_id': identity, 'task': view['task'],
            'native_attempt_status': record['attempt_status'],
            'native_attempt_outcome': record['attempt_outcome'],
            'native_task_station': evidence['task_station'],
            'projected_lifecycle': view['lifecycle']['mapped'],
            'process_at_acquisition': evidence['process'], 'lifecycle_evidence': 'source_record',
            'progress': 'unknown', 'tool_activity': 'unsupported', 'retry': 'not_requested',
            'agrees': True, 'agreement_basis': 'retained_prior_fact' if retained_prior else 'current',
            **({'retained_lifecycle': fact.lifecycle.mapped, 'lifecycle_quality': 'unknown',
                'reconcile_latched': True} if retained_prior else {})})
    if (projection['native_write_enabled'] or saved.reducer.roles[observer.binding.role].complete
            or saved.reducer.summary(observer.binding.role, now=now)['availability'] != 'unknown'):
        raise ValueError('Partial native observation promoted to runtime availability/control')
    return {'source_projection_agreement': True, 'compared_attempts': len(comparisons),
        'comparisons': comparisons, 'native_snapshot_complete': work.complete,
        'truncated_tables': work.truncated_tables, 'native_event_cursor': work.latest_event_id,
        'atomic_runtime_watermark': None, 'runtime_coverage': 'partial',
        'acquisition_evidence': {'original_acquired_at': snapshot.acquired_at,
            'epoch': ingest._epoch, 'source_cursor': cursor,
            'immutable_acquisition_identity_verified': True},
        'role_availability': 'unknown', 'native_write_enabled': False}
