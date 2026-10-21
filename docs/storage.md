# A08 Workshop historian and recovery

This is an in-process, synthetic-tested storage slice, not a running service,
HTTP/SSE binding, collector or interoperability claim. A10's separate bounded
read-only SQLite primitive (not a native schema adapter) is in `source-binding.md`.
It uses the Python standard library and the existing reducer/ingress contracts.

## Ownership and transaction model

`Storage(path, initial=State(reducer, ingests), retention=128)` creates a new
Workshop-owned file. Reopening uses `Storage(path, retention=128)`; initial
configuration is not silently substituted for persisted configuration. Supply
retention explicitly on each open if using a value other than the default.
Only a local filesystem supporting SQLite WAL is supported. One service owns
one writer; calls are serial on that connection/thread. Do not open a second
Storage as a passive reader: opening an existing historian is a service-start
operation that invalidates live state. Snapshot/replay methods use short read
transactions on the service connection; WAL also permits separate SQLite read
connections without taking its writer lock.

The initial migration is `backend/workshop/migrations/001_initial.sql`.
`application_id` and `user_version=1` identify this schema. Nonempty foreign
files and unsupported versions are rejected before WAL/schema mutations.
Never point Storage at a native actor database. Fixture databases exist only
under pytest temporary paths, including the foreign/native-shaped fixture.
This historian is separate from the A10 read-only source acquisition primitive.

WAL + `synchronous=FULL`, short `BEGIN IMMEDIATE` writer transactions and atomic
commits persist domain tables and one monotonically increasing service revision
together. Tables retain roles/signals, feeds, execution identities/native/mapped
observations/conflicts, correlations, ambiguities, alarm rules/controls,
occurrences/audit, ingress identity hashes/order/epochs/diagnostics and source
watermarks. The JSON codec has a closed type allowlist; no pickle, eval or class
imports from stored names. Restoration reconnects alarm occurrence/control and
current-occurrence identities, including pending delays and incident counters.

`read()` returns detached State; its Ingest objects share that detached reducer.
Changing it does not persist. `with storage.transaction() as state:` stages
trusted Workshop-local configuration, signal, clock and alarm changes. Exceptions,
serialization errors and SQL failures roll back domain state and revision.
Keep these transactions short: no network calls or waits inside them. Never
feed raw native/wire observations through this local escape hatch; it trusts
already-approved domain data, just as Reducer does. Native observations use
`storage.cloudevents(...)` or `storage.otlp(...)`, which validate/redact before
persisting state and the replay journal. No raw request, prompt, body, tool
argument/result or unknown content is saved. A failed call does not consume
identity hashes or a source cursor.

Use `LocalAPI(storage=storage)` for durable operator acknowledgement. Existing
`LocalAPI(reducer)` remains an explicitly in-memory fixture facade. Authorization
and viewer/operator/controller restrictions are unchanged; acknowledgement never
clears a source condition, and no position enables native writes.

## Source snapshot contract and races

Each stored Ingest requires a dedicated configured source, role, feed and runtime
instance identity. The binding must already exist; no identity is discovered
from a producer. A10 task instance/namespace allowlists are enforced by the same
validator on durable snapshot pages; see `source-binding.md`. Snapshot/domain
records use Ingest's existing execution data schema, not a replacement
CloudEvents envelope.

The trusted adapter supplies two DIFFERENT cursor domains:

- `source_cursor` to each durable ingress call: a positive, monotonically
  increasing integer in that adapter's source stream, stable across collector
  restarts. A same-cursor retry is permitted only for duplicate/no-new records.
  Cursor regression requests reconciliation, not arbitrary reordering. The
  adapter must translate native cursors/epoch resets into this stable sequence;
  these are not execution revisions, occurrence times, receipt times or CE
  extensions. Sparse monotonic cursors are permitted; this layer cannot infer
  missing native observations merely from an integer jump.
- `watermark` on a source snapshot: the adapter's inclusive source-stream
  boundary captured atomically with the snapshot. It cannot precede the source
  cursor already committed when collection begins. It may be ahead of delivered
  events. The adapter must actually provide that atomic boundary; Storage cannot
  manufacture source consistency from unrelated paginated reads.

The serial adapter calls:

1. `begin_snapshot(name, generation=..., scope=(...), epoch=..., watermark=...,
   acquired_at=..., pages=('a', 'b'), complete=True) -> token` before receiving
   the snapshot pages/events that can race. This captures the pre-snapshot
   service revision. Generations increase per source; a new generation retires
   its old token. Scope must be a nonempty subset of the registered role scope.
   The epoch must match the current acquired source epoch (or an unobserved
   source), never a retired one. Acquisition is caller-supplied original capture
   time, not last-page receipt.
2. `snapshot_page(token, page_id, [domain_record, ...])`. Pages are durable but
   do not mutate the domain projection. Identical retry pages are idempotent;
   changed contents, undeclared pages, duplicate execution identities within or
   across pages and unsupported extra domain fields reject. Up to 64 pages,
   256 records/page, 1 MiB/page, 64 KiB/record; no unbounded page buffering.
3. `finish_snapshot(token)` atomically publishes only after every manifest page
   arrives. A full-scope, declared-complete, runtime-observed snapshot with
   supported lifecycle mappings can replace current inventory and clear the
   ingress reconciliation latch. Reported/inferred/operator/source-record
   absence cannot establish runtime availability, including an empty snapshot.

The retained post-BEGIN ingress journal replays membership/order above the
source watermark. Newer effective canonical keys retain their already-reduced
fields; the snapshot does not roll back history and does not double-apply those
events. Ignored/duplicate records cannot shadow a missed terminal repair.
Conflicts and identity changes still pass through reducer discrepancy handling,
even when a newer canonical field is protected. Other sources' conflicting
observations and disputed sets are never erased by source reconciliation.
Snapshot generation/scope/watermark/epoch/acquisition/completeness are journaled.

Complete absence removes a key only from current role inventory, not execution
history. An omitted nonterminal execution loses live acquisition freshness;
absence never fabricates succeeded/failed/cancelled. Terminal observations,
identity hashes, conflicts and alarm audit remain retained. Partial scope,
`complete=False` or unsupported mappings merge without removing unseen execution
objects/presence, degrade coverage and leave reconciliation required. Partial
snapshot records cannot restore live freshness, particularly after restart.

If the source epoch changes during assembly, the bounded journal expires, a
record's native revision regresses, pages are missing, or a local/configuration/
alarm mutation overlaps the collection window, completion raises
`RecoveryRequired` without replacing the domain. The caller obtains a fresh
snapshot/generation; it must not spin on the old token. The local-change gate is
intentionally conservative: an operator acknowledgement is never lost to an
in-flight snapshot. Snapshot retries cannot bypass source ordering or role
signal prerequisites.

## Service and browser restart

Opening an existing historian retains facts, identities, order indexes,
collector/retired epochs, alarms and audit, but clears feed/live-execution/signal
acquisition freshness and complete coverage, sets each ingress reconciliation
latch and discards unfinished snapshot jobs. It commits that invalidation as a
new revision before serving reads. Clock values are supplied by a trusted caller;
the domain never reads a wall clock. Alarm pending deadlines retain the caller's
acquisition-clock values, so the caller must keep that clock domain comparable
across service restarts. New collector epochs still invalidate their own source
as in the earlier ingress slice. Neither transport traffic nor ordinary events
can clear the reconciliation latch. Complete source reacquisition does not
refresh unrelated admission/reachability/capacity signals; those must be acquired
again before availability is possible.

`snapshot(now=...)` returns `{cursor, projection}` in one SQLite read view.
The cursor is Workshop-database identity + committed service revision, unrelated
to source cursors. `replay(cursor, now=...)` returns ordered immutable projection
checkpoints strictly after it; apply them in order through the returned last
cursor before presenting the final current projection. Re-evaluate with an
explicit caller acquisition clock; history/receipt does not advance freshness.
A cursor at the current revision yields no entries. Malformed, foreign,
future or expired cursors raise `RecoveryRequired`: obtain one fresh atomic
snapshot, not a replay storm. Backend source history is not deleted by a browser
reconnect. HTTP/SSE and browser code remain later bindings of this in-process
contract, not implemented here.

## Bounds and limitations

Replay checkpoints/journal retain at most `retention` service revisions (default
128); pending snapshots retain one generation per source with the page bounds
above. A snapshot taking longer than retained replay history must restart.
Domain history, observations, alarm audit and identity/order indexes are retained,
not pruned by that setting. Each revision currently stores a full domain
checkpoint and domain table writes are straightforward replacements: this is
correctness-first Phase 1, not a demonstrated high-volume historian or a disk
quota/archival policy. Retention count does not claim a byte/time bound for all
durable history. No bounded collector outbox, online-backup command, concurrent
worker queue, native schema adapter, HTTP/auth/CSRF layer, renderer or binary
OTLP codec is included. Never delete dedup identity independently of retained
source replay semantics. No external dependency was added or installed.

## Verification

Run the existing Python 3.11+ pytest environment from the repository root:

    python -m pytest -q
    python -m pytest -q backend/tests/test_storage.py backend/tests/test_storage_edges.py
    python -m compileall -q backend
    git diff --check

See `evidence/STORAGE_REVIEW.md` and `a08-*.txt` for actual red/green output,
signed red baseline, adversarial history/provenance regressions, SQL-failure
rollback, abrupt child-process exit/WAL recovery and concurrent snapshot/cursor
read-view verification. All fixtures are synthetic; no native/live operational
acceptance, frontend, transport, certification or coverage-percentage claim.
