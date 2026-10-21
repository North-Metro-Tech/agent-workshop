# SPDX-License-Identifier: Apache-2.0
"""Scoped read-only Kanban attempts plus independent process corroboration.

No execution discovery from /proc, native helpers, hooks or agent control.
Attempt facts remain source_record even with a matching live PID. A native DB
snapshot plus later proc reads has NO atomic runtime watermark. This collector
therefore never attempts complete runtime recovery or asserts availability.
"""
from dataclasses import dataclass
import json

from workshop.contracts import FeedPolicy, timestamp
from workshop.ingest import Acquisition, Ingest, SourceBinding, HERMES_VALUES
from workshop.reducer import Reducer
from workshop.storage import State
from .hermes_work import HermesWork

MAPPING_VERSION = 'hermes-runtime-v1'


def runtime_binding(scope):
    """Trusted configuration for one board instance, not producer authority."""
    identity = scope.source_instance + '/' + scope.board + '/kanban-attempts'
    return SourceBinding(source='urn:agentworkshop:hermes:' + identity,
        runtime=identity, role=identity, feed=identity, evidence_class='source_record',
        task_scopes=((scope.source_instance, scope.board),))


def initial_state(binding, scope):
    """Fresh dedicated service state; reopening Storage uses its saved binding."""
    r = Reducer()
    r.register_role(binding.role, scope=(scope.board,), inventory_approved=False)
    r.register_feed(binding.feed, FeedPolicy(5, 15, 30), group=binding.feed)
    return State(r, {'runtime': Ingest(r, binding)})


def _label(field, value):
    return value if isinstance(value, str) and value in HERMES_VALUES[field] else 'unknown'


def _lifecycle(run):
    # Completion of an ATTEMPT is not task acceptance or process death.
    if run['ended_at'] is None:
        return 'active' if run['status'] == 'running' else 'unknown'
    if run['status'] == 'done':
        return {'completed': 'succeeded', 'failed': 'failed',
                'cancelled': 'cancelled'}.get(run['outcome'], 'unknown')
    return 'unknown'


@dataclass(frozen=True)
class RuntimeSnapshot:
    binding: SourceBinding
    acquired_at: float
    native_complete: bool
    native_event_cursor: int
    source_identity: tuple[int, int]
    _observations_json: str
    # These constants are deliberately not parameters an adapter can promote.
    atomic_watermark = None
    runtime_complete = False
    runtime_coverage = 'partial'

    def observations(self):
        """Detached safe evidence, not native rows or a runtime inventory."""
        return json.loads(self._observations_json)

    def _payload(self, epoch, cursor):
        logs = []
        for item in self.observations():
            attrs = {
                'workshop.record.id': json.dumps([epoch, cursor, item['execution_id']]),
                'workshop.execution.id': item['execution_id'],
                # Native source has no Hermes conversation/session ID. This is
                # a namespaced attempt context, never a claimed session match.
                'workshop.session.id': item['attempt_context'],
                'workshop.lifecycle': item['lifecycle'],
                **{'workshop.task.' + k: v for k, v in item['task'].items()},
                'workshop.hermes.mapping.version': MAPPING_VERSION,
                'workshop.hermes.process': item['process'],
                'workshop.hermes.process.reason': item['process_reason'],
                'workshop.hermes.attempt.status': item['attempt_status'],
                'workshop.hermes.attempt.outcome': item['attempt_outcome'],
                'workshop.hermes.task.station': item['task_station'],
                'workshop.hermes.board.event_id': self.native_event_cursor,
                'workshop.hermes.native.complete': self.native_complete,
            }
            logs.append({'attributes': [{'key': k, 'value':
                {'boolValue' if type(v) is bool else 'intValue' if type(v) is int else 'stringValue': v}}
                for k, v in attrs.items()]})
        payload = {'resourceLogs': [{'scopeLogs': [{'scope':
            {'name': 'workshop.hermes_runtime', 'version': MAPPING_VERSION}, 'logRecords': logs}]}]}
        return json.dumps(payload, ensure_ascii=False, allow_nan=False).encode()


class HermesRuntime:
    def __init__(self, work, binding):
        if not isinstance(work, HermesWork) or not isinstance(binding, SourceBinding):
            raise ValueError('Explicit work adapter and trusted binding required')
        if binding.evidence_class != 'source_record':
            raise ValueError('Kanban attempt lifecycle requires source_record authority')
        self.work, self.binding = work, binding

    def observe(self, *, board, acquired_at):
        snapshot = self.work.observe(board=board, acquired_at=acquired_at)
        records = []
        for run in snapshot._tables['task_runs']:
            if type(run['id']) is not int or run['id'] <= 0 or not isinstance(run['task_id'], str):
                raise ValueError('Invalid native attempt identity')
            execution = snapshot.execution(run['id'])
            process = snapshot.inspect(run['id'])
            records.append({'execution_id': str(run['id']),
                'attempt_context': 'kanban-attempt/' + str(run['id']),
                'task': {'source_instance': snapshot.source_instance,
                         'namespace': snapshot.board, 'native_id': run['task_id']},
                'lifecycle': _lifecycle(run), 'lifecycle_evidence': 'source_record',
                'process': execution['process'], 'process_reason': process['reason'],
                'task_station': execution['task_station'],
                'attempt_status': _label('workshop.hermes.attempt.status', run['status']),
                'attempt_outcome': _label('workshop.hermes.attempt.outcome', run['outcome']),
                'progress': 'unknown', 'tool_activity': 'unsupported', 'retry': 'not_requested'})
        identity = self.work._source_identity
        if identity is None:
            raise RuntimeError('Native acquisition supplied no source file identity')
        return RuntimeSnapshot(self.binding, snapshot.acquired_at, snapshot.complete,
            snapshot.latest_event_id, identity,
            json.dumps(records, ensure_ascii=False, allow_nan=False))

    def publish(self, storage, name, snapshot, *, received_at, epoch, source_cursor):
        """One serial writer call through bounded OTLP validation, not raw domain writes.

        Caller owns a stable durable collector-stream sequence. Board event IDs
        are diagnostic metadata only: proc readings may change without an event.
        The later outbox owns offline buffering; this adapter never buffers/retries.
        """
        if (not isinstance(snapshot, RuntimeSnapshot) or snapshot.binding != self.binding
                or storage.read().ingests[name].binding != self.binding):
            raise ValueError('Snapshot/historian binding mismatch')
        if type(source_cursor) is not int or not 1 <= source_cursor < 2**63:
            raise ValueError('Positive stable collector source cursor required')
        timestamp(received_at)
        if received_at < snapshot.acquired_at:
            raise ValueError('Receipt precedes snapshot acquisition')
        context = Acquisition(snapshot.acquired_at, received_at, epoch)
        return storage.otlp(name, 'logs', snapshot._payload(epoch, source_cursor),
                            context=context, source_cursor=source_cursor,
                            source_identity=snapshot.source_identity)

    def quality(self, *, now):
        return self.work.quality(now=now)
