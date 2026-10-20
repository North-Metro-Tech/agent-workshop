# SPDX-License-Identifier: Apache-2.0
"""Synthetic A07/A09 wire fixtures; no transport, databases or producer content."""
from copy import deepcopy
import json

import pytest

from workshop.contracts import ExecutionKey, FeedPolicy
from workshop.ingest import Acquisition, EVENT_TYPE, Ingest, SourceBinding
from workshop.reducer import Reducer


@pytest.fixture
def ingest():
    r = Reducer()
    r.register_role('agent', scope=('chat',), inventory_approved=True)
    r.register_feed('runtime', FeedPolicy(15, 45, 120), group='source')
    return Ingest(r, SourceBinding('urn:fixture:source', 'runtime-a', 'agent', 'runtime'))


def context(at=10, receipt=None, epoch='boot-a', receipt_unix=None):
    return Acquisition(at, at if receipt is None else receipt, epoch, receipt_unix)


def event(id='event-1', state='active', execution='exec-1', revision=1):
    return {'specversion': '1.0', 'source': 'urn:fixture:source', 'id': id,
            'type': EVENT_TYPE, 'data': {'execution_id': execution,
            'session_id': 'session-1', 'lifecycle': state, 'revision': revision}}


def wire(value):
    return json.dumps(value).encode()


def attrs(values):
    return [{'key': k, 'value': {'intValue' if type(v) is int else 'stringValue':
            str(v) if type(v) is int else v}} for k, v in values.items()]


def logs(id='log-1', state='active', revision=1):
    a = {'workshop.execution.id': 'exec-1', 'workshop.session.id': 'session-1',
         'workshop.lifecycle': state, 'workshop.revision': revision}
    if id is not None:
        a['workshop.record.id'] = id
    return {'resourceLogs': [{'resource': {'attributes': attrs({'service.instance.id': 'fixture'})},
        'scopeLogs': [{'scope': {'name': 'synthetic', 'version': '1'},
        'logRecords': [{'timeUnixNano': '1000000000', 'attributes': attrs(a)}]}]}]}


def traces(state=None, end='2000000000', status=1):
    a = {'gen_ai.operation.name': 'invoke_agent', 'gen_ai.agent.id': 'agent',
         'workshop.execution.id': 'exec-1', 'workshop.session.id': 'session-1'}
    if state is not None:
        a['workshop.lifecycle'] = state
    return {'resourceSpans': [{'scopeSpans': [{'spans': [{
        'traceId': '11' * 16, 'spanId': '22' * 8,
        'startTimeUnixNano': '1000000000', 'endTimeUnixNano': end,
        'attributes': attrs(a), 'status': {'code': status}}]}]}]}


def record(i):
    return i.reducer.executions[ExecutionKey('runtime-a', 'exec-1')]


def submit(i, protocol, state='active', id='one', revision=1, ctx=None):
    ctx = ctx or context()
    if protocol == 'ce':
        return i.cloudevents(wire(event(id, state, revision=revision)), context=ctx)
    return i.otlp('logs', wire(logs(id, state, revision)), context=ctx)


@pytest.mark.parametrize('protocol', ['ce', 'logs'])
def test_A07_duplicate_is_noop_not_a_freshness_heartbeat(ingest, protocol):
    submit(ingest, protocol)
    result = submit(ingest, protocol, ctx=context(90))
    assert result.duplicates == 1
    assert len(ingest.reducer.executions) == 1
    assert len(record(ingest).observations) == 1
    assert record(ingest).acquired_at == 10
    assert ingest.reducer.feeds['runtime'].last_acquired_at == 10


@pytest.mark.parametrize('protocol', ['ce', 'logs'])
def test_A07_changed_body_reuse_rejected_without_mutation(ingest, protocol):
    submit(ingest, protocol)
    before = deepcopy((ingest.reducer.roles, ingest.reducer.feeds,
                       ingest.reducer.executions, ingest.reducer.alarms.__dict__))
    with pytest.raises(ValueError, match='identity'):
        submit(ingest, protocol, state='failed', ctx=context(20))
    assert (ingest.reducer.roles, ingest.reducer.feeds,
            ingest.reducer.executions, ingest.reducer.alarms.__dict__) == before
    assert len(ingest.records) == 1


@pytest.mark.parametrize('protocol', ['ce', 'logs'])
def test_A07_out_of_order_revision_and_terminal_guard(ingest, protocol):
    submit(ingest, protocol, state='succeeded', revision=3)
    submit(ingest, protocol, id='old', revision=2, ctx=context(20))
    submit(ingest, protocol, id='late', revision=4, ctx=context(30))
    assert record(ingest).lifecycle.mapped == 'succeeded'
    assert len(ingest.reducer.executions) == 1


@pytest.mark.parametrize('protocol', ['ce', 'logs'])
def test_A07_older_native_revision_cannot_regress_nonterminal(ingest, protocol):
    submit(ingest, protocol, state='stopping', revision=4)
    result = submit(ingest, protocol, state='starting', id='old', revision=2, ctx=context(20))
    assert record(ingest).lifecycle.mapped == 'stopping'
    assert result.ignored == 1
    assert ingest.reducer.feeds['runtime'].last_acquired_at == 10


@pytest.mark.parametrize('protocol', ['ce', 'logs'])
def test_A09_backlog_uses_original_acquisition_never_receipt(ingest, protocol):
    submit(ingest, protocol, ctx=context(10, 1000))
    assert record(ingest).acquired_at == 10
    assert ingest.reducer.summary('agent', now=1000)['active_executions'] == []
    assert ingest.reducer.feed_quality('runtime', now=1000) == 'disconnected'
    assert ingest.records[0]['received_at'] == 1000
    assert ingest.records[0]['acquired_at'] == 10


@pytest.mark.parametrize('protocol', ['ce', 'logs'])
def test_A09_unknown_acquisition_cannot_establish_freshness(ingest, protocol):
    submit(ingest, protocol, ctx=context(None, 1000))
    assert record(ingest).acquired_at is None
    assert ingest.reducer.feed_quality('runtime', now=1000) == 'unknown'
    assert ingest.reducer.summary('agent', now=1000)['active_executions'] == []


@pytest.mark.parametrize('protocol', ['ce', 'logs'])
def test_A09_source_restart_invalidates_old_live_state(ingest, protocol):
    submit(ingest, protocol)
    submit(ingest, protocol, id='restart', revision=1, ctx=context(20, epoch='boot-b'))
    assert ingest.reconcile_required
    assert 'source_restart' in ingest.diagnostics
    assert record(ingest).acquired_at is None
    assert ingest.reducer.summary('agent', now=20)['active_executions'] == []
    submit(ingest, protocol, id='old-epoch', revision=100, ctx=context(30))
    assert ingest.reducer.summary('agent', now=30)['active_executions'] == []
    assert 'retired_epoch' in ingest.diagnostics


@pytest.mark.parametrize('protocol', ['ce', 'logs'])
def test_A09_acquisition_clock_skew_is_diagnosed_not_fresh(ingest, protocol):
    submit(ingest, protocol, ctx=context(200, 100))
    assert 'acquisition_clock_skew' in ingest.diagnostics
    assert record(ingest).acquired_at is None
    assert ingest.reducer.summary('agent', now=200)['active_executions'] == []


def test_A09_source_time_skew_does_not_set_acquisition_clock(ingest):
    e = event()
    e['time'] = '2030-01-01T00:00:00Z'
    ingest.cloudevents(wire(e), context=context(10, receipt_unix=1))
    assert 'source_clock_skew' in ingest.diagnostics
    assert record(ingest).acquired_at is None
    assert ingest.records[0]['occurrence_at'] > 1


def test_A07_ce_optional_standard_fields_are_optional(ingest):
    ingest.cloudevents(wire(event()), context=context())
    assert record(ingest).lifecycle.mapped == 'active'
    assert ingest.records[0]['occurrence_at'] is None


def test_A07_ce_preserves_parent_task_and_native_provenance(ingest):
    e = event()
    e['time'] = '2026-01-01T00:00:00+00:00'
    e['data'].update(parent_execution_id='parent',
                     task={'source_instance': 'tasks', 'namespace': 'board', 'native_id': '7'})
    ingest.cloudevents(wire(e), context=context())
    assert record(ingest).parent == ExecutionKey('runtime-a', 'parent')
    assert record(ingest).task.namespace == 'board'
    assert record(ingest).lifecycle.native == 'active'
    assert record(ingest).lifecycle.observed_at == ingest.records[0]['occurrence_at']
    assert record(ingest).lifecycle.mapping_version


@pytest.mark.parametrize('change', [
    {'specversion': '1.0.2'}, {'specversion': 1}, {'source': 'urn:other'},
    {'source': ''}, {'source': 'not a uri'}, {'id': ''}, {'id': 1},
    {'type': 'other'}, {'type': ''}, {'time': 'tomorrow'},
    {'time': '2026-01-01T00:00:00'}, {'datacontenttype': 'text/plain'},
    {'data': []}, {'data': None}, {'data_base64': 'e30='},
    {'subject': 7}, {'dataschema': 'not a uri'},
])
def test_A07_ce_invalid_envelope_rejected(ingest, change):
    e = event()
    e.update(change)
    with pytest.raises(ValueError):
        ingest.cloudevents(wire(e), context=context())
    assert ingest.reducer.executions == {}
    assert ingest.records == []


@pytest.mark.parametrize('field', ['id', 'source', 'type', 'specversion', 'data'])
def test_A07_ce_required_fields(ingest, field):
    e = event()
    del e[field]
    with pytest.raises(ValueError):
        ingest.cloudevents(wire(e), context=context())


@pytest.mark.parametrize('change', [
    {'execution_id': ''}, {'session_id': ''}, {'revision': True}, {'revision': -1},
    {'parent_execution_id': []}, {'task': {'native_id': '7'}},
    {'canonical': 'spoof'}, {'prompt': 'synthetic private sentinel'},
])
def test_A07_domain_schema_rejects_malformed_or_unapproved_fields(ingest, change):
    e = event()
    e['data'].update(change)
    with pytest.raises(ValueError):
        ingest.cloudevents(wire(e), context=context())
    assert not ingest.reducer.executions


@pytest.mark.parametrize('payload', [b'{', b'null', b'42', b'{}\xff',
    b'{"id":"a","id":"b"}', b'{"x":NaN}', b'[]' * 50000,
    b'[' * 1000 + b']' * 1000],
    ids=['truncated', 'null', 'scalar', 'utf8', 'duplicate-key', 'nan', 'many-values', 'deep'])
def test_A07_malformed_json_rejected(ingest, payload):
    with pytest.raises(ValueError):
        ingest.cloudevents(payload, context=context())


def test_A07_unknown_native_lifecycle_retained_unknown(ingest):
    ingest.cloudevents(wire(event(state='future-native-state')), context=context())
    assert record(ingest).lifecycle.native == 'future-native-state'
    assert record(ingest).lifecycle.mapped == 'unknown'
    assert not record(ingest).lifecycle.supported
    assert not ingest.reducer.summary('agent', now=10)['active_executions']


def test_A07_batch_atomic_on_invalid_last_record(ingest):
    bad = event('bad', execution='exec-2')
    bad['data']['session_id'] = ''
    with pytest.raises(ValueError):
        ingest.cloudevents(wire([event(), bad]), context=context())
    assert not ingest.reducer.executions
    assert not ingest.records
    ingest.cloudevents(wire(event()), context=context())
    assert len(ingest.reducer.executions) == 1


@pytest.mark.parametrize('limit', ['event', 'batch', 'request'])
def test_A07_size_and_batch_limits(ingest, limit):
    if limit == 'event':
        e = event()
        e['extension'] = 'x' * (64 * 1024)
        payload = wire(e)
    elif limit == 'batch':
        payload = wire([event(str(n)) for n in range(257)])
    else:
        payload = b' ' * (1024 * 1024 + 1)
    with pytest.raises(ValueError):
        ingest.cloudevents(payload, context=context())
    assert not ingest.reducer.executions


def test_A07_ce_identity_is_source_and_id_not_json_byte_order(ingest):
    e = event()
    ingest.cloudevents(wire(e), context=context())
    result = ingest.cloudevents(json.dumps(e, sort_keys=True, indent=2).encode(), context=context(20))
    assert result.duplicates == 1


def test_A07_unordered_acquisitions_do_not_regress_feed(ingest):
    ingest.cloudevents(wire(event()), context=context(20))
    ingest.cloudevents(wire(event('two', execution='exec-2')), context=context(10, 30))
    assert len(ingest.reducer.executions) == 2
    assert ingest.reducer.feeds['runtime'].last_acquired_at == 20
    assert ingest.reducer.executions[ExecutionKey('runtime-a', 'exec-2')].acquired_at == 10


def test_A07_no_revision_orders_by_acquisition_not_receipt(ingest):
    a, b = event(), event('old', state='starting')
    del a['data']['revision']
    del b['data']['revision']
    ingest.cloudevents(wire(a), context=context(20))
    ingest.cloudevents(wire(b), context=context(10, 30))
    assert record(ingest).lifecycle.mapped == 'active'


def test_A07_otlp_and_ce_share_native_execution_identity(ingest):
    submit(ingest, 'ce')
    submit(ingest, 'logs', id='terminal', state='succeeded', revision=2, ctx=context(20))
    assert len(ingest.reducer.executions) == 1
    assert record(ingest).lifecycle.mapped == 'succeeded'


def test_A07_log_without_record_id_is_corroboration_not_inventory(ingest):
    result = ingest.otlp('logs', wire(logs(None)), context=context())
    assert result.corroborated == 1
    assert not ingest.reducer.executions
    assert ingest.reducer.feed_quality('runtime', now=10) == 'unknown'


@pytest.mark.parametrize('status,mapped', [(1, 'succeeded'), (2, 'failed'), (0, 'unknown')])
def test_A07_completed_span_is_terminal_evidence_not_live_inventory(ingest, status, mapped):
    ingest.otlp('traces', wire(traces(status=status)), context=context(10, 1000))
    assert record(ingest).lifecycle.mapped == mapped
    assert not ingest.reducer.summary('agent', now=1000)['active_executions']
    assert ingest.records[0]['trace_id'] == '11' * 16
    assert ingest.records[0]['span_id'] == '22' * 8


def test_A07_open_span_never_proves_current_liveness(ingest):
    result = ingest.otlp('traces', wire(traces(state='active', end='0')), context=context())
    assert result.corroborated == 1
    assert not ingest.reducer.executions


def test_A07_completed_span_cannot_claim_active_from_native_attribute(ingest):
    with pytest.raises(ValueError):
        ingest.otlp('traces', wire(traces(state='active')), context=context())


def test_A07_span_identity_dedup_and_changed_content_rejection(ingest):
    p = wire(traces())
    ingest.otlp('traces', p, context=context())
    assert ingest.otlp('traces', p, context=context(20)).duplicates == 1
    with pytest.raises(ValueError, match='identity'):
        ingest.otlp('traces', wire(traces(status=2)), context=context(30))
    assert record(ingest).lifecycle.mapped == 'succeeded'


@pytest.mark.parametrize('mutation', ['trace', 'span', 'time', 'schema', 'duplicate_attr', 'nan_attr'])
def test_A07_otlp_malformed_mapping_rejected(ingest, mutation):
    p = traces()
    scope = p['resourceSpans'][0]['scopeSpans'][0]
    span = scope['spans'][0]
    if mutation == 'trace':
        span['traceId'] = '0' * 32
    elif mutation == 'span':
        span['spanId'] = 'xyz'
    elif mutation == 'time':
        span['startTimeUnixNano'] = '3000000000'
    elif mutation == 'schema':
        scope['schemaUrl'] = 'https://opentelemetry.io/schemas/unsupported'
    elif mutation == 'duplicate_attr':
        span['attributes'].append(deepcopy(span['attributes'][0]))
    else:
        span['attributes'].append({'key': 'bad', 'value': {'doubleValue': float('nan')}})
    with pytest.raises(ValueError):
        ingest.otlp('traces', wire(p), context=context())
    assert not ingest.reducer.executions


def test_A07_otlp_redacts_content_before_retaining(ingest):
    p = logs()
    log = p['resourceLogs'][0]['scopeLogs'][0]['logRecords'][0]
    log['body'] = {'stringValue': 'synthetic private sentinel'}
    log['attributes'] += attrs({'gen_ai.input.messages': 'synthetic private sentinel',
                                'gen_ai.tool.call.arguments': 'synthetic private sentinel'})
    ingest.otlp('logs', wire(p), context=context())
    assert 'synthetic private sentinel' not in repr(ingest.records)
    assert 'synthetic private sentinel' not in repr(ingest.reducer.__dict__)
    assert ingest.records[0]['resource']['service.instance.id'] == 'fixture'


@pytest.mark.parametrize('signal', ['metrics', 'other'])
def test_A07_unsupported_otlp_signal_explicitly_rejected(ingest, signal):
    with pytest.raises(ValueError):
        ingest.otlp(signal, b'{}', context=context())


def test_A07_rejected_batch_does_not_restart_or_touch_diagnostics(ingest):
    submit(ingest, 'ce')
    before = deepcopy(ingest.diagnostics)
    with pytest.raises(ValueError):
        ingest.cloudevents(wire([event('new'), event('bad', revision=-1)]),
                           context=context(20, epoch='boot-b'))
    assert ingest.diagnostics == before
    assert not ingest.reconcile_required
    assert record(ingest).acquired_at == 10
