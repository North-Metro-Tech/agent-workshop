# SPDX-License-Identifier: Apache-2.0
"""Adversarial ingress regressions, using only synthetic protocol fixtures."""
from copy import deepcopy
import pytest

from test_ingest import ingest, context, event, wire, logs, traces, record, submit
from workshop.api import LocalAPI


@pytest.mark.parametrize('protocol', ['ce', 'logs'])
def test_A09_duplicate_after_restart_still_invalidates_old_live_state(ingest, protocol):
    submit(ingest, protocol)
    submit(ingest, protocol, ctx=context(20, epoch='boot-b'))
    assert ingest.reconcile_required
    assert 'source_restart' in ingest.diagnostics
    assert not ingest.reducer.summary('agent', now=20)['active_executions']


def test_A09_snapshot_represents_unknown_age_without_crashing(ingest):
    submit(ingest, 'ce', ctx=context(None, 100))
    e = LocalAPI(ingest.reducer).snapshot(now=100)['executions'][0]
    assert e['acquisition_age'] is None
    assert e['lifecycle_quality'] == 'unknown'


@pytest.mark.parametrize('protocol', ['ce', 'logs'])
def test_A09_terminal_fact_without_known_acquisition_is_not_delayed(ingest, protocol):
    submit(ingest, protocol)
    submit(ingest, protocol, id='ended', revision=2, state='failed', ctx=context(None, 20))
    assert record(ingest).lifecycle.mapped == 'failed'
    assert record(ingest).acquired_at is None


@pytest.mark.parametrize('protocol', ['ce', 'logs'])
def test_A07_newer_native_revision_is_authority_not_capture_clock(ingest, protocol):
    submit(ingest, protocol, state='active', revision=1, ctx=context(20))
    submit(ingest, protocol, state='stopping', revision=2, id='two', ctx=context(10, 30))
    assert record(ingest).lifecycle.mapped == 'stopping'
    assert record(ingest).acquired_at == 10
    assert ingest.reducer.feeds['runtime'].last_acquired_at == 20


def test_A07_open_span_does_not_poison_completed_span_identity(ingest):
    ingest.otlp('traces', wire(traces(end='0')), context=context())
    ingest.otlp('traces', wire(traces()), context=context(20))
    assert record(ingest).lifecycle.mapped == 'succeeded'


@pytest.mark.parametrize('content_type', [7, None, [], {}])
def test_A07_malformed_content_type_rejected_as_validation_error(ingest, content_type):
    e = event()
    e['datacontenttype'] = content_type
    with pytest.raises(ValueError):
        ingest.cloudevents(wire(e), context=context())


def test_A07_json_content_type_parameters_valid(ingest):
    e = event()
    e['datacontenttype'] = 'application/json; charset=utf-8'
    ingest.cloudevents(wire(e), context=context())
    assert record(ingest).lifecycle.mapped == 'active'


@pytest.mark.parametrize('extension', [{'bad-name': 1}, {'nested': {}}, {'fraction': 1.5}])
def test_A07_malformed_ce_context_extension_rejected(ingest, extension):
    e = event()
    e.update(extension)
    with pytest.raises(ValueError):
        ingest.cloudevents(wire(e), context=context())


@pytest.mark.parametrize('location', ['body', 'attribute'])
def test_A07_malformed_otlp_anyvalue_rejected(ingest, location):
    p = logs()
    item = p['resourceLogs'][0]['scopeLogs'][0]['logRecords'][0]
    if location == 'body':
        item['body'] = {'notAValue': 'synthetic'}
    else:
        item['attributes'].append({'key': 'ignored', 'value': {'bytesValue': '!!!invalid'}})
    with pytest.raises(ValueError):
        ingest.otlp('logs', wire(p), context=context())


def test_A07_empty_otlp_request_validates_trusted_context(ingest):
    with pytest.raises(ValueError):
        ingest.otlp('logs', b'{}', context=None)


def test_A07_otlp_batch_rolls_back_later_changed_identity(ingest):
    submit(ingest, 'logs')
    p = logs('new')
    items = p['resourceLogs'][0]['scopeLogs'][0]['logRecords']
    items += deepcopy(logs('one', 'failed')['resourceLogs'][0]['scopeLogs'][0]['logRecords'])
    before = deepcopy(ingest.records)
    with pytest.raises(ValueError, match='identity'):
        ingest.otlp('logs', wire(p), context=context(20))
    assert ingest.records == before
    assert record(ingest).lifecycle.mapped == 'active'


def test_A07_standard_genai_span_without_domain_identity_is_corroboration(ingest):
    p = traces()
    span = p['resourceSpans'][0]['scopeSpans'][0]['spans'][0]
    span['attributes'] = [a for a in span['attributes'] if not a['key'].startswith('workshop.')]
    result = ingest.otlp('traces', wire(p), context=context())
    assert result.corroborated == 1
    assert not ingest.reducer.executions


def test_A07_log_retains_occurrence_and_source_observed_times_separately(ingest):
    p = logs()
    log = p['resourceLogs'][0]['scopeLogs'][0]['logRecords'][0]
    log['observedTimeUnixNano'] = '3000000000'
    ingest.otlp('logs', wire(p), context=context(10, 100))
    assert ingest.records[0]['occurrence_at'] == 1
    assert ingest.records[0]['source_observed_at'] == 3
    assert ingest.records[0]['received_at'] == 100


@pytest.mark.parametrize('protocol', ['ce', 'logs'])
def test_A09_unknown_order_does_not_hide_terminal_fact(ingest, protocol):
    if protocol == 'ce':
        a, b = event(), event('ended', state='failed')
        del a['data']['revision']
        del b['data']['revision']
        ingest.cloudevents(wire(a), context=context())
        ingest.cloudevents(wire(b), context=context(None, 20))
    else:
        a, b = logs(), logs('ended', 'failed')
        for p in (a, b):
            log = p['resourceLogs'][0]['scopeLogs'][0]['logRecords'][0]
            log['attributes'] = [v for v in log['attributes'] if v['key'] != 'workshop.revision']
        ingest.otlp('logs', wire(a), context=context())
        ingest.otlp('logs', wire(b), context=context(None, 20))
    assert record(ingest).lifecycle.mapped == 'failed'


@pytest.mark.parametrize('value', [None, False, 0, 1.5, 'wrong', {}])
def test_A07_nested_otlp_shape_errors_are_value_errors(ingest, value):
    with pytest.raises(ValueError):
        ingest.otlp('logs', wire({'resourceLogs': value}), context=context())


def test_A07_maximum_batch_and_otlp_bounds(ingest):
    accepted = ingest.cloudevents(wire([event(str(n), execution=str(n)) for n in range(256)]),
                                context=context())
    assert accepted.accepted == 256
    p = logs()
    scope = p['resourceLogs'][0]['scopeLogs'][0]
    scope['logRecords'] *= 257
    with pytest.raises(ValueError, match='256'):
        ingest.otlp('logs', wire(p), context=context(20))
    with pytest.raises(ValueError):
        ingest.otlp('logs', b' ' * (1024 * 1024 + 1), context=context(20))
    assert len(ingest.reducer.executions) == 256


@pytest.mark.parametrize('field', ['name', 'version'])
def test_A07_scope_metadata_cannot_retain_arbitrary_nested_content(ingest, field):
    p = logs()
    scope = p['resourceLogs'][0]['scopeLogs'][0]['scope']
    scope[field] = {'prompt': 'synthetic private sentinel'}
    with pytest.raises(ValueError):
        ingest.otlp('logs', wire(p), context=context())
    assert not ingest.records
