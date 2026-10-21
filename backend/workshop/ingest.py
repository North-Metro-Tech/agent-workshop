# SPDX-License-Identifier: Apache-2.0
"""Bounded function-level CloudEvents and decoded OTLP JSON observation mapping.

No listener or protobuf codec: a future transport uses maintained OTLP bindings,
not a Workshop envelope. SourceBinding and Acquisition are trusted local inputs,
NEVER fields accepted from an event producer. See docs/ingest.md for the mapping,
clock domains, supported subset, immutable pins and deliberate limitations.
"""
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
import base64
import binascii
import hashlib
import json
import re
from urllib.parse import urlsplit

from .contracts import ExecutionKey, Observation, TaskKey, timestamp
from .reducer import ACTIVE, LIFECYCLE, TERMINAL, Reducer

EVENT_TYPE = 'org.agentworkshop.execution.lifecycle.v1'
MAPPING_VERSION = 'workshop-ingest-v1'
SPAN_MERGE_POLICY = 'immutable-completed-span-v1'
MAX_EVENT = 64 * 1024
MAX_REQUEST = 1024 * 1024
MAX_BATCH = 256
MAX_DEPTH = 64
SKEW_TOLERANCE = 45
DOMAIN_FIELDS = {'execution_id', 'session_id', 'lifecycle', 'parent_execution_id',
                 'task', 'revision'}
RESOURCE_FIELDS = {'service.name', 'service.namespace', 'service.instance.id'}
ATTRIBUTE_FIELDS = {'gen_ai.operation.name', 'gen_ai.agent.id', 'gen_ai.agent.name',
                    'gen_ai.tool.name', 'gen_ai.request.model', 'gen_ai.response.model',
                    'gen_ai.provider.name', 'workshop.execution.id', 'workshop.session.id',
                    'workshop.parent_execution.id', 'workshop.lifecycle', 'workshop.revision',
                    'workshop.record.id', 'workshop.cursor', 'workshop.task.source_instance',
                    'workshop.task.namespace', 'workshop.task.native_id'}


def _text(value, label):
    if not isinstance(value, str) or not value.strip() or len(value) > 4096:
        raise ValueError(f'Invalid {label}')
    if any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError(f'Invalid {label}')
    return value


def _uri(value, label):
    _text(value, label)
    if any(c.isspace() for c in value) or re.search(r'%(?![0-9a-fA-F]{2})', value):
        raise ValueError(f'Invalid {label}')
    try:
        urlsplit(value)
    except ValueError as exc:
        raise ValueError(f'Invalid {label}') from exc
    return value


def _object(value, label):
    if not isinstance(value, dict):
        raise ValueError(f'Invalid {label}')
    return value


def _array(value, label):
    if not isinstance(value, list):
        raise ValueError(f'Invalid {label}')
    return value


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False).encode('utf-8')


def _digest(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON field')
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError('Non-finite JSON number')


def _decode(payload):
    if not isinstance(payload, bytes) or len(payload) > MAX_REQUEST:
        raise ValueError('Request must be bytes within 1 MiB')
    try:
        value = json.loads(payload.decode('utf-8'), object_pairs_hook=_pairs,
                           parse_constant=_reject_constant)
        stack = [(value, 0)]
        while stack:
            item, depth = stack.pop()
            if depth > MAX_DEPTH:
                raise ValueError('JSON nesting limit exceeded')
            if isinstance(item, dict):
                stack.extend((v, depth + 1) for v in item.values())
            elif isinstance(item, list):
                stack.extend((v, depth + 1) for v in item)
            elif isinstance(item, float):
                timestamp(item)
        # Also reject unpaired surrogates, even in ignored extension fields.
        _canonical(value)
        return value
    except (UnicodeError, RecursionError, OverflowError) as exc:
        raise ValueError('Malformed or excessively nested JSON') from exc


def _rfc3339(value):
    _text(value, 'CloudEvents time')
    if not re.fullmatch(r'\d{4}-\d\d-\d\d[Tt]\d\d:\d\d:\d\d(?:\.\d+)?(?:[Zz]|[+-]\d\d:\d\d)', value):
        raise ValueError('CloudEvents time requires RFC3339 timezone')
    try:
        return datetime.fromisoformat(value.upper().replace('Z', '+00:00')).timestamp()
    except (ValueError, OverflowError) as exc:
        raise ValueError('Invalid CloudEvents time') from exc


def _uint(value, label):
    if isinstance(value, str) and re.fullmatch(r'[0-9]+', value):
        value = int(value)
    if type(value) is not int or not 0 <= value < 2**64:
        raise ValueError(f'Invalid {label}')
    return value


def _hex(value, length, label, *, optional=False):
    if optional and value in (None, ''):
        return None
    if not isinstance(value, str) or not re.fullmatch('[0-9a-fA-F]{' + str(length) + '}', value):
        raise ValueError(f'Invalid {label}')
    if int(value, 16) == 0:
        raise ValueError(f'Invalid zero {label}')
    return value.lower()


def _attributes(value):
    result = {}
    for pair in _array(value, 'OTLP attributes'):
        pair = _object(pair, 'OTLP attribute')
        key = _text(pair.get('key'), 'OTLP attribute key')
        if key in result:
            raise ValueError('Duplicate OTLP attribute')
        av = _object(pair.get('value'), 'OTLP AnyValue')
        if len(av) != 1:
            raise ValueError('OTLP AnyValue requires one value')
        kind, item = next(iter(av.items()))
        if kind == 'stringValue' and isinstance(item, str):
            result[key] = item
        elif kind == 'intValue':
            if isinstance(item, str) and re.fullmatch(r'-?[0-9]+', item):
                item = int(item)
            if type(item) is not int or not -(2**63) <= item < 2**63:
                raise ValueError('Invalid OTLP intValue')
            result[key] = item
        elif kind == 'boolValue' and type(item) is bool:
            result[key] = item
        elif kind == 'doubleValue' and type(item) in (int, float):
            timestamp(item)
            result[key] = item
        elif kind == 'arrayValue':
            # Validate native nested AnyValues without retaining content.
            for nested in _array(_object(item, 'arrayValue').get('values', []), 'array values'):
                _attributes([{'key': '_', 'value': nested}])
            result[key] = None
        elif kind == 'kvlistValue':
            _attributes(_object(item, 'kvlistValue').get('values', []))
            result[key] = None
        elif kind == 'bytesValue' and isinstance(item, str):
            try:
                base64.b64decode(item, validate=True)
            except (ValueError, binascii.Error) as exc:
                raise ValueError('Invalid OTLP bytesValue') from exc
            result[key] = None
        else:
            raise ValueError('Unsupported or malformed OTLP AnyValue')
    return result


@dataclass(frozen=True)
class SourceBinding:
    source: str
    runtime: str
    role: str
    feed: str
    schema_url: str = ''
    evidence_class: str = 'runtime_observed'
    # Explicit trusted task-link permissions. Empty means no task links, never
    # a wildcard. An origin's own source label does not grant another board.
    task_scopes: tuple[tuple[str, str], ...] = ()

    def __post_init__(self):
        _uri(self.source, 'configured source')
        for label in ('runtime', 'role', 'feed'):
            _text(getattr(self, label), label)
        if self.schema_url:
            _uri(self.schema_url, 'configured schema URL')
        if self.evidence_class not in {'runtime_observed', 'source_record', 'agent_reported',
                                       'operator_recorded', 'inferred'}:
            raise ValueError('Unknown evidence class')
        if not isinstance(self.task_scopes, tuple) or len(self.task_scopes) > MAX_BATCH:
            raise ValueError('Task scopes require a bounded immutable allowlist')
        for scope in self.task_scopes:
            if not isinstance(scope, tuple) or len(scope) != 2:
                raise ValueError('Task scope requires source instance and namespace')
            for value in scope:
                _text(value, 'configured task scope')
        if len(set(self.task_scopes)) != len(self.task_scopes):
            raise ValueError('Duplicate configured task scope')


@dataclass(frozen=True)
class Acquisition:
    acquired_at: float | None
    received_at: float
    epoch: str
    receipt_unix: float | None = None

    def __post_init__(self):
        if self.acquired_at is not None:
            timestamp(self.acquired_at)
        timestamp(self.received_at)
        if self.receipt_unix is not None:
            timestamp(self.receipt_unix)
        _text(self.epoch, 'collector epoch')


@dataclass
class IngestResult:
    accepted: int = 0
    duplicates: int = 0
    ignored: int = 0
    corroborated: int = 0


class Ingest:
    """One configured source/scope, sharing the existing reducer's actor identity.

    Calls are serial, in-memory transactions. Standalone identity/order indexes
    survive only this object's lifetime; Storage wraps them for durable atomic
    replay/snapshot recovery without retaining incoming wire content.
    """
    def __init__(self, reducer: Reducer, binding: SourceBinding):
        if binding.role not in reducer.roles or binding.feed not in reducer.feeds:
            raise ValueError('Bind only registered role and feed')
        self.reducer = reducer
        self.binding = binding
        self.records = []
        self.diagnostics = []
        self.reconcile_required = False
        self._epoch = None
        self._retired_epochs = set()
        self._seen = {}
        self._ordering = {}

    def _diagnose(self, code):
        if code not in self.diagnostics:
            self.diagnostics.append(code)

    def _context(self, ctx):
        if not isinstance(ctx, Acquisition):
            raise ValueError('Trusted Acquisition context required')
        if ctx.epoch in self._retired_epochs:
            self._diagnose('retired_epoch')
            return None, False
        if self._epoch is not None and ctx.epoch != self._epoch:
            self._retired_epochs.add(self._epoch)
            self.reconcile_required = True
            self._diagnose('source_restart')
            self._ordering.clear()
            # The binding owns this feed. Invalidate its live field evidence;
            # leave unrelated sources/feeds and retained terminal facts alone.
            self.reducer.feeds[self.binding.feed].last_acquired_at = None
            for execution in self.reducer.executions.values():
                if (execution.lifecycle.source == self.binding.source
                        and execution.lifecycle.mapped not in TERMINAL):
                    execution.acquired_at = None
            for role in self.reducer.roles.values():
                if role.reconcile_feed == self.binding.feed:
                    role.complete = False
                    role.reconciled_at = None
                for name, (observation, _) in list(role.signals.items()):
                    if observation.source == self.binding.source:
                        role.signals[name] = (observation, None)
        self._epoch = ctx.epoch
        acquired = ctx.acquired_at
        if acquired is not None and acquired > ctx.received_at:
            self._diagnose('acquisition_clock_skew')
            acquired = None
        if self.reconcile_required:
            acquired = None
        if acquired is None:
            self._diagnose('acquisition_unknown')
        return acquired, True

    def _transaction(self, records, context):
        # Validate and map every record before touching either the live reducer
        # or indexes. Stage application too: downstream domain errors roll back.
        if not isinstance(context, Acquisition):
            raise ValueError('Trusted Acquisition context required')
        if len(records) > MAX_BATCH:
            raise ValueError('Batch exceeds 256 observations')
        staged = deepcopy(self)
        result = IngestResult()
        applied = []
        for index, record in enumerate(records):
            before = result.accepted
            staged._apply(record, context, result)
            if result.accepted > before:
                applied.append(index)
        self.reducer.__dict__.update(staged.reducer.__dict__)
        staged.reducer = self.reducer
        self.__dict__.update(staged.__dict__)
        # Bounded, validated/redacted records for the Workshop historian's
        # transactional replay journal. Never the incoming wire bytes/content.
        self._last_batch = (deepcopy(records), context)
        self._last_effects = tuple(applied)
        return result

    def _apply(self, record, ctx, result):
        identity, digest = record['identity'], record['digest']
        acquired, usable_epoch = self._context(ctx)
        if identity is not None and identity in self._seen:
            if self._seen[identity] != digest:
                raise ValueError('Changed content for existing observation identity')
            result.duplicates += 1
            return
        if identity is not None:
            self._seen[identity] = digest
        if not usable_epoch:
            result.ignored += 1
            return
        occurrence = record['occurrence_at']
        if (occurrence is not None and ctx.receipt_unix is not None
                and occurrence > ctx.receipt_unix + SKEW_TOLERANCE):
            self._diagnose('source_clock_skew')
            acquired = None
        metadata = {k: deepcopy(v) for k, v in record.items()
                    if k not in {'domain', 'identity'}}
        metadata.update(source=self.binding.source, epoch=ctx.epoch,
                        acquired_at=acquired, received_at=ctx.received_at,
                        mapping_version=MAPPING_VERSION)
        self.records.append(metadata)
        if record['domain'] is None:
            result.corroborated += 1
            return
        domain = record['domain']
        key = ExecutionKey(self.binding.runtime, domain['execution_id'])
        canonical = self.reducer.correlations.get(key, (key, ''))[0]
        revision = domain.get('revision')
        previous_order = self._ordering.get(canonical)
        if previous_order is not None:
            old_revision, old_acquired = previous_order
            if revision is not None and old_revision is not None:
                obsolete = revision <= old_revision
            else:
                obsolete = acquired is None or (old_acquired is not None and acquired <= old_acquired)
                # Unknown acquisition cannot prove a live update is newer, but
                # must not hide a terminal fact for this same execution. Native
                # revision ordering, when present on both records, still wins.
                if domain['lifecycle'] in TERMINAL:
                    obsolete = False
            if obsolete:
                result.ignored += 1
                return
        parent = domain.get('parent_execution_id')
        task = domain.get('task')
        native = domain['lifecycle']
        mapped = native if native in LIFECYCLE else 'unknown'
        observation = Observation(native, mapped, MAPPING_VERSION,
            self.binding.source, self.binding.feed, occurrence,
            supported=native in LIFECYCLE, evidence_class=self.binding.evidence_class)
        self.reducer.observe_execution(self.binding.role, key, session=domain['session_id'],
            parent=ExecutionKey(self.binding.runtime, parent) if parent else None,
            task=TaskKey(**task) if task else None,
            lifecycle=observation, acquired_at=acquired, source_ordered=True)
        self._ordering[canonical] = (revision, acquired)
        result.accepted += 1

    def _domain(self, data):
        data = _object(data, 'execution lifecycle data')
        if set(data) - DOMAIN_FIELDS:
            raise ValueError('Unapproved execution lifecycle data field')
        for field in ('execution_id', 'session_id', 'lifecycle'):
            _text(data.get(field), field)
        if 'revision' in data and (type(data['revision']) is not int or data['revision'] < 0):
            raise ValueError('Invalid native revision')
        if 'parent_execution_id' in data:
            _text(data['parent_execution_id'], 'parent_execution_id')
        if 'task' in data:
            task = _object(data['task'], 'task')
            if set(task) != {'source_instance', 'namespace', 'native_id'}:
                raise ValueError('Task requires composite identity')
            for name, value in task.items():
                _text(value, name)
            if (task['source_instance'], task['namespace']) not in self.binding.task_scopes:
                raise ValueError('Task link outside configured source scope')
        return deepcopy(data)

    def cloudevents(self, payload: bytes, *, context: Acquisition) -> IngestResult:
        value = _decode(payload)
        batch = value if isinstance(value, list) else [value]
        if not batch or len(batch) > MAX_BATCH:
            raise ValueError('CloudEvents batch requires 1..256 events')
        records = []
        for event in batch:
            event = _object(event, 'CloudEvent')
            if len(_canonical(event)) > MAX_EVENT:
                raise ValueError('Domain event exceeds 64 KiB')
            if event.get('specversion') != '1.0':
                raise ValueError('CloudEvents specversion must be 1.0')
            _text(event.get('id'), 'CloudEvents id')
            _uri(event.get('source'), 'CloudEvents source')
            if event['source'] != self.binding.source:
                raise ValueError('CloudEvents source outside configured scope')
            if event.get('type') != EVENT_TYPE:
                raise ValueError('Unsupported CloudEvents type')
            if 'data_base64' in event:
                raise ValueError('Only JSON domain data supported')
            content_type = _text(event.get('datacontenttype', 'application/json'), 'datacontenttype')
            if content_type.split(';', 1)[0].strip().lower() != 'application/json':
                raise ValueError('Only application/json domain data supported')
            standard = {'specversion', 'id', 'source', 'type', 'data', 'subject',
                        'time', 'dataschema', 'datacontenttype'}
            for name, value in event.items():
                if name in standard:
                    continue
                if (not re.fullmatch(r'[a-z0-9]+', name)
                        or type(value) not in (str, int, bool)):
                    raise ValueError('Invalid CloudEvents extension context attribute')
                if type(value) is int and not -(2**31) <= value < 2**31:
                    raise ValueError('CloudEvents Integer out of range')
            if 'subject' in event:
                _text(event['subject'], 'CloudEvents subject')
            if 'dataschema' in event:
                _uri(event['dataschema'], 'CloudEvents dataschema')
                if event['dataschema'] != 'urn:agentworkshop:execution-lifecycle:v1':
                    raise ValueError('Unsupported domain schema')
            occurrence = _rfc3339(event['time']) if 'time' in event else None
            records.append({'identity': ('ce', event['source'], event['id']),
                'digest': _digest(event), 'domain': self._domain(event.get('data')),
                'occurrence_at': occurrence, 'protocol': 'cloudevents',
                'native_id': event['id']})
        return self._transaction(records, context)

    def otlp(self, signal: str, payload: bytes, *, context: Acquisition) -> IngestResult:
        if signal not in {'logs', 'traces'}:
            raise ValueError('Unsupported OTLP signal')
        value = _object(_decode(payload), 'OTLP export request')
        resource_name, scope_name, record_name = (
            ('resourceLogs', 'scopeLogs', 'logRecords') if signal == 'logs'
            else ('resourceSpans', 'scopeSpans', 'spans'))
        if set(value) - {resource_name}:
            raise ValueError('Unsupported OTLP export request fields')
        records = []
        for resource in _array(value.get(resource_name, []), resource_name):
            resource = _object(resource, resource_name)
            self._schema(resource)
            native_resource = _object(resource.get('resource', {}), 'resource')
            resource_attributes = _attributes(native_resource.get('attributes', []))
            safe_resource = {k: v for k, v in resource_attributes.items() if k in RESOURCE_FIELDS}
            for scope in _array(resource.get(scope_name, []), scope_name):
                scope = _object(scope, scope_name)
                self._schema(scope)
                native_scope = _object(scope.get('scope', {}), 'scope')
                for field in ('name', 'version'):
                    if field in native_scope:
                        scope_value = native_scope[field]
                        if not isinstance(scope_value, str):
                            raise ValueError('OTLP scope metadata must be strings')
                        if scope_value:
                            _text(scope_value, 'OTLP scope ' + field)
                _attributes(native_scope.get('attributes', []))
                for item in _array(scope.get(record_name, []), record_name):
                    if len(records) >= MAX_BATCH:
                        raise ValueError('OTLP batch exceeds 256 observations')
                    item = _object(item, record_name)
                    attributes = _attributes(item.get('attributes', []))
                    if signal == 'logs' and 'body' in item:
                        _attributes([{'key': '_body', 'value': item['body']}])
                    safe = {k: v for k, v in attributes.items() if k in ATTRIBUTE_FIELDS}
                    record = self._otlp_record(signal, item, safe)
                    # Hash before redaction, including native resource/scope,
                    # but never retain sensitive content or body/status text.
                    record.update(digest=_digest([native_resource, native_scope,
                        resource.get('schemaUrl', ''), scope.get('schemaUrl', ''), item]),
                        resource=safe_resource, attributes=safe,
                        resource_schema_url=resource.get('schemaUrl', ''),
                        schema_url=scope.get('schemaUrl', ''),
                        scope={k: native_scope[k] for k in ('name', 'version') if k in native_scope})
                    records.append(record)
        return self._transaction(records, context)

    def _schema(self, value):
        url = value.get('schemaUrl', '')
        if not isinstance(url, str) or url not in ('', self.binding.schema_url):
            raise ValueError('Unsupported OTLP schema URL')

    def _otlp_record(self, signal, item, attributes):
        trace = _hex(item.get('traceId'), 32, 'trace ID', optional=signal == 'logs')
        span = _hex(item.get('spanId'), 16, 'span ID', optional=signal == 'logs')
        domain = None
        observed_nanos = 0
        if signal == 'logs':
            nanos = _uint(item.get('timeUnixNano', '0'), 'log time')
            observed_nanos = _uint(item.get('observedTimeUnixNano', '0'), 'log observed time')
            record_id = attributes.get('workshop.record.id', attributes.get('workshop.cursor'))
            if record_id is not None:
                _text(record_id, 'stable log record ID')
            identity = ('log', self.binding.source, record_id) if record_id is not None else None
            eligible = identity is not None and 'workshop.lifecycle' in attributes
        else:
            start = _uint(item.get('startTimeUnixNano', '0'), 'span start time')
            nanos = _uint(item.get('endTimeUnixNano', '0'), 'span end time')
            if nanos and (not start or nanos < start):
                raise ValueError('Invalid span time interval')
            _hex(item.get('parentSpanId'), 16, 'parent span ID', optional=True)
            status = _object(item.get('status', {}), 'span status').get('code', 0)
            if type(status) is not int or status not in (0, 1, 2):
                raise ValueError('Invalid span status')
            # An unfinished span is corroboration, not an immutable terminal
            # export. Do not let it poison the eventual completed-span ID.
            identity = ('span', self.binding.source, trace, span) if nanos else None
            eligible = (bool(nanos) and 'workshop.session.id' in attributes
                        and attributes.get('gen_ai.operation.name') in {'invoke_agent', 'invoke_workflow'})
            if nanos and attributes.get('workshop.lifecycle') in ACTIVE:
                raise ValueError('Completed span cannot establish active lifecycle')
            if eligible:
                attributes = dict(attributes)
                attributes['workshop.lifecycle'] = attributes.get('workshop.lifecycle',
                    {0: 'unknown', 1: 'succeeded', 2: 'failed'}[status])
                # Native execution mapping preferred. Never infer parentage from
                # trace relationships or equate agent ID with execution ID.
                attributes.setdefault('workshop.execution.id', f'{trace}/{span}')
        if eligible:
            domain = {'execution_id': attributes.get('workshop.execution.id'),
                      'session_id': attributes.get('workshop.session.id'),
                      'lifecycle': attributes.get('workshop.lifecycle')}
            for attr, name in [('workshop.revision', 'revision'),
                               ('workshop.parent_execution.id', 'parent_execution_id')]:
                if attr in attributes:
                    domain[name] = attributes[attr]
            task = {name: attributes['workshop.task.' + name] for name in
                    ('source_instance', 'namespace', 'native_id') if 'workshop.task.' + name in attributes}
            if task:
                domain['task'] = task
            domain = self._domain(domain)
        return {'identity': identity, 'domain': domain,
                'occurrence_at': nanos / 1_000_000_000 if nanos else None,
                'source_observed_at': observed_nanos / 1_000_000_000 if observed_nanos else None,
                'protocol': 'otlp-' + signal, 'trace_id': trace, 'span_id': span,
                'merge_policy': SPAN_MERGE_POLICY if signal == 'traces' else MAPPING_VERSION}
