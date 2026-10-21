# Function-level ingress — mapping v1

This is the A07/A09 synthetic ingress slice, not a listening service, durable
historian, collector, or interoperability certification. All methods are serial
in-memory calls. No source is contacted, and no clock is read by the domain.
Exact reference pins and the Core-resolved supplied GenAI revision are recorded in
`standards.lock`; there is deliberately no dependency installation.

## Local API and trust boundary

```python
from workshop.ingest import Acquisition, Ingest, SourceBinding

# r is the existing Reducer with this role/feed already registered.
ingest = Ingest(r, SourceBinding(
    source='urn:fixture:source', runtime='runtime-a', role='agent', feed='runtime'))
result = ingest.cloudevents(payload_bytes, context=Acquisition(
    acquired_at=10, received_at=1000, epoch='boot-a'))
# Or: ingest.otlp('logs', otlp_json_bytes, context=...)
# Or: ingest.otlp('traces', otlp_json_bytes, context=...)
```

SourceBinding is trusted configuration, not inferred from `source`, resource
attributes, display names, `gen_ai.agent.id`, or a producer's principal field.
Provision a dedicated feed for the binding and keep one Ingest object for that
source/scope. Multiple bindings may share a reducer, not an ingress feed.
Execution keys use the configured runtime and native execution ID. Only the
reducer's explicit local correlation mappings can alias them. Task keys retain
source instance + namespace + native ID; parentage is explicit native execution
parentage, never inferred from a trace, timing or name similarity.

Acquisition is service/collector-owned context and must never be populated from
untrusted event attributes. The caller supplies original successful acquisition
and receipt in the SAME acquisition-clock domain, plus collector epoch. If the
capture timestamp cannot be translated to that domain, use None. Receipt time
never substitutes for acquisition. Optional receipt_unix is trusted UTC seconds
for diagnosing future source occurrence timestamps; it cannot establish freshness.
CloudEvents `time` and OTLP occurrence/source-observed times are source clocks,
not comparable ordering authorities or acquisition clocks. Absence stays None.

## CloudEvents

Input is UTF-8 JSON bytes: a structured event, or the standard JSON event array.
The four standard required context attributes are required: nonempty `id`,
URI-reference `source`, known `type`, and `specversion='1.0'`. Relevant domain
`data` is required; optional standard context fields remain optional. There is
no `kind` or replacement envelope. Source must match the configured origin.

Supported type: `org.agentworkshop.execution.lifecycle.v1`. Its JSON data is:

- execution_id, session_id, lifecycle: nonempty strings;
- revision: optional nonnegative native integer revision;
- parent_execution_id: optional explicit native parent ID;
- task: optional object with exactly source_instance, namespace, native_id.

No additional data fields are accepted. Canonical lifecycle names are the
existing reducer states; unknown native names stay native + mapped unknown,
with supported=False. If provided, dataschema must equal
`urn:agentworkshop:execution-lifecycle:v1`. JSON content type parameters are
accepted; non-JSON and data_base64 are unsupported, not silently converted.
Time is timezone-qualified RFC3339. Extensions must have lowercase alphanumeric
names and supported scalar CloudEvents context values. Unused context and
extensions are hashed for identity checks, not retained as arbitrary content.

Identity is (source, id), independent of collector epoch. Hashes use sorted-key
canonical JSON, so whitespace/object-key order alone do not change identity.
Changed content under the same ID is rejected before any transaction commits.
A retry is a no-op: it cannot refresh a feed or a field's acquisition clock.

## OTLP observation mapping

Input is the existing OTLP JSON export request shape: resourceSpans/scopeSpans/
spans or resourceLogs/scopeLogs/logRecords. This is NOT OTLP wrapped in CE.
Only traces and logs are supported; metrics are explicitly rejected. Native
hex trace/span IDs, integer enums, string/integer nanosecond timestamps, standard
resource and instrumentation-scope metadata, and schemaUrl are used. This is a
function-level JSON mapper, NOT a binary-protobuf parser or HTTP binding. The
future transport must use maintained protobuf definitions/SDKs, not this mapper
as an excuse to build a handwritten protobuf decoder. No SDK compatibility or
binary codec test is claimed here.

A configured nonempty schema_url permits that exact producer schema URL;
unspecified URLs remain explicitly unspecified. Other schema URLs are rejected.
Resource and scope schema URLs, native source times, receipt, acquisition,
epoch, trace/span IDs and mapping/merge-policy versions remain separate.

Allowed mapping attributes:

- Standard: gen_ai.operation.name, gen_ai.agent.id, gen_ai.agent.name,
  gen_ai.tool.name, gen_ai.request.model, gen_ai.response.model,
  gen_ai.provider.name. Resource: service.name, service.namespace,
  service.instance.id. Other content attributes are discarded before retention.
- Domain-only: workshop.execution.id, workshop.session.id,
  workshop.parent_execution.id, workshop.lifecycle, workshop.revision,
  workshop.record.id, workshop.cursor, workshop.task.source_instance,
  workshop.task.namespace, workshop.task.native_id.

An identified lifecycle log requires workshop.record.id or a stable string
workshop.cursor, unique within the configured source scope. The producer/adapter
must make cursors stable across epoch resets, e.g. by including its native
stream identity. Logs without stable identity remain corroboration only:
they create no actor, replace no inventory and do not advance process freshness.

Span identity is configured source scope + trace ID + span ID. The versioned
merge policy is immutable-completed-span-v1: exact retries deduplicate;
changed completed exports are rejected. An unfinished span is corroboration
only and cannot poison its eventual completed export. Completed invoke_agent /
invoke_workflow spans with explicit workshop.session.id map to execution
terminal evidence: OK → succeeded, ERROR → failed, UNSET → unknown. A mapped
native terminal lifecycle may be supplied explicitly. An active lifecycle on a
completed span is rejected. Explicit execution ID is preferred; otherwise that
span's trace/span pair is its native execution identity. Standard GenAI spans
without the session mapping remain valid corroboration rather than being forced
to invent a session or emit a second protocol. Other spans are corroboration.
No span establishes current active inventory, available capacity, delegation,
useful progress or independently accepted work.

## Ordering, clocks and restart

Ordering is only within a configured source and native execution: compare known
native revisions, otherwise original acquisitions. Out-of-order observations
are retained as redacted provenance but cannot regress current state or refresh
its feed. Unknown-order live updates cannot claim a newer state. A terminal fact
without a comparable capture time is retained, never delayed by silence. An
explicit older native revision is still ignored. Reducer terminal and authority
conflict invariants remain in force. Native revision permission is an internal
trusted source_ordered argument, not a producer flag. No cross-authority wall
clock ordering or receipt-order authority is introduced.

Original acquisition times remain attached to individual executions; a late
record for another execution cannot rewind the feed. Missing capture time is
represented by None/unknown age in the domain and read facade, never a fabricated
zero or recent receipt. A future acquisition diagnoses acquisition_clock_skew
and removes live freshness from that record. A source occurrence more than 45
seconds ahead of optional receipt_unix diagnoses source_clock_skew and similarly
cannot refresh current state. This tolerance is an engineering setting, not a
standard requirement. Late/backlogged occurrence is allowed; its original
capture still controls freshness. Without a trusted UTC anchor, source clock
skew is not claimed to have been measured.

Changing collector epoch diagnoses source_restart, invalidates source/feed live
evidence and complete coverage, and sets reconcile_required. Even a duplicate
first event of the new epoch triggers this invalidation. Retired epochs cannot
reactivate the source. Terminal history remains terminal. No event clears the
reconciliation latch: complete-scope snapshot recovery belongs to the next Phase
1 storage slice via `Storage`; see `storage.md`. Standalone Ingest objects remain
in-memory and cannot clear the latch themselves. Restart recovery is deliberately
conservative, not fabricated liveness.

## Bounds, privacy and atomicity

Requests are at most 1 MiB of actual input bytes; domain events at most 64 KiB
of canonical UTF-8 JSON; both paths accept at most 256 observations per call.
OTLP's request/count bounds are configured here independently of CE event size.
JSON nesting is capped at 64; invalid UTF-8, duplicate JSON keys, invalid native
IDs/times/AnyValues, non-finite numbers, and unsupported mapping shapes reject
as ValueError. Empty OTLP export requests are no-ops, not acquisition heartbeats.

Validation and redaction happen before live state changes. A staged transaction
includes identity indexes, source epoch/diagnostics and the reducer; failure of
any item rolls back the whole batch. The bounded call does not persist raw
messages, body/status text, prompts, reasoning, tool arguments/results or unknown
resource content. Hashes detect changed content before redaction; only bounded
allowlisted metadata and mapped observations remain. Review identity fields as
source metadata, not trusted display HTML/URLs.

Standalone Ingest state/indexes are in memory and grow with accepted history.
`Storage` now persists them alongside the reducer atomically, and keeps a bounded
validated/redacted replay journal; use its ingress methods for durable calls.
The private `_last_batch`/`_last_effects` values expose only the last bounded
validated call and its effective-record indices to that historian, never raw
wire content. Deduplication identity and retained domain history are not evicted
by replay retention. This is not a collector outbox. No live data, native
databases, renderer or control path is part of these tests.
