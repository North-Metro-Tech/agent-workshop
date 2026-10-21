# Hermes runtime observations and durable correlation (Phase 2 slice 2)

This slice observes the SAME explicitly approved board as `hermes_work`, using
its bounded read-only native transaction and optional boot/PID/start-verified
Linux process probe. It does not discover Hermes session databases, other boards,
cron stores, processes, environments, attachments, command lines or credentials.
No native helper import, write, hook, agent control or native dependency exists.

## Evidence and identity

`HermesRuntime(HermesWork(scope, process_probe=...), runtime_binding(scope))`
produces a detached immutable `RuntimeSnapshot`. The binding is trusted local
configuration with dedicated source/feed/role/runtime identities derived from
source instance + board + `kanban-attempts`, and a composite `task_scopes`
allowlist for that source instance and board. The role is an observation role,
not a claim to know the inventory/availability of every executor profile.

Each native task-run ID becomes a runtime-scoped execution ID and namespaced
`kanban-attempt/<id>` context. That context is NOT a Hermes conversation/session
ID. Its composite task link contains source instance, board and native task ID.
Attempt exit, task station and independently verified process liveness remain
separate facts. A matching PID/start identity corroborates process liveness,
never a particular session, execution activity, progress or tool call.

The versioned mapping `hermes-runtime-v1` uses bounded OTLP JSON log attributes:

- Running attempt with no end time -> `active`, evidence `source_record`.
- Ended, `done` attempt with `completed` / `failed` / `cancelled` outcome ->
  `succeeded` / `failed` / `cancelled`, evidence `source_record`.
- Other status/outcome combinations -> lifecycle `unknown`. Native disposition
  remains in separate finite allowlisted metadata; review/blocked is NOT success
  or permanent failure. Silence, dead/reused/missing/denied PIDs and acknowledgments
  never manufacture terminal lifecycle, progress, retries or recovery.
- Process metadata is exactly `alive`, `not_alive` or `unknown`, plus a finite
  reviewed reason. No PID, start fingerprint or free-form native payload is sent.
- Tool activity is unsupported; progress is unknown; no retry is requested.

The canonical lifecycle's evidence class now follows the trusted binding, rather
than being silently promoted to `runtime_observed`. Existing runtime-observed
bindings retain their previous semantics. Hermes metadata is finite, all-or-none,
source-record-only and requires scoped task/attempt/context identity. A10 applies
to metadata-only records too; an empty task scope denies the whole batch.

## Serial durable path and recovery boundary

`observer.publish(storage, 'runtime', snapshot, received_at=..., epoch=...,
source_cursor=...)` calls the existing `Storage.otlp` serial transaction. It does
not mutate reducer state directly or bypass payload/scope/privacy validation.
Stored execution identity, task links, redacted metadata, cursor, dedup and epoch
state survive service restart atomically. Invalid batches roll back together.

The caller owns the collector epoch and positive durable stream sequence; use
identical snapshot/epoch/sequence for retry. Changed observation needs a new
sequence even when the native board event cursor did not advance. The source
cursor is NOT a native revision, runtime watermark, per-record revision, nor a
license to rebuild acquisition time from receipt. The later outbox owns buffering
and retry. This adapter neither buffers nor retries. Caller acquisition clocks
must remain comparable under the standing A08 contract; the opt-in proof utility
uses the current host's monotonic clock, not a cross-host/reboot clock protocol.

The existing adapter already rejects source-file replacement during an observer
lifetime. This slice also binds the acquired `(device, inode)` to the configured
ingest in the SAME historian transaction as the observations/cursor. Restart
cannot silently correlate recycled native IDs after file replacement. A bound
identity cannot be changed or omitted; an already-observed source without durable
provenance cannot silently adopt one. Use explicit new configured source/runtime
and historian ownership, not automatic rebinding. Older historians without this
optional field remain readable for their original non-file-identity-bound feeds.
This is a trusted-filesystem identity fence, not a hostile TOCTOU, inode-reuse or
in-place-backup-restore detector.

The board-local event cursor shares the native table transaction, but process
reads happen AFTER it. They have NO common atomic runtime watermark. Therefore:

- `RuntimeSnapshot.atomic_watermark` is always `None`.
- Runtime coverage is always `partial`; `runtime_complete` is always false.
- Even native table completeness cannot authorize complete runtime recovery.
- The role starts with inventory coverage unapproved and availability unknown.
- Reopening `Storage` is a service restart: disk-resurrected active freshness is
  invalidated and reconciliation is latched. Ordinary observations, including a
  matching process, do NOT clear that latch. Complete source-record snapshots
  cannot clear it either. There is intentionally no fake runtime snapshot here.
- The existing complete, supported runtime-observed recovery protocol remains
  available to an adapter that actually has the required atomic evidence; its
  race/scope/loss/replay tests remain part of the regression suite.

Persisted process attributes are historical records with original acquisition
context, not a fresh current-process API. Restore re-establishes observation,
NOT readiness or runtime availability from disk.

## Opt-in actual live evidence

No normal test, demo, check or install reads the live board. Explicit command:

```
python3 scripts/observe_runtime.py --approved-local
```

It samples only `approved_scope()`, uses one service writer, stores its private
historian under git-ignored `.workshop-state/hermes-runtime.db`, validates durable
readback and outputs only counts, reviewed labels and native main/schema hashes.
It also sends the SAME actual observation through an empty task allowlist in a
separate disposable Workshop historian, verifies rejection and unchanged durable
state, then removes only that disposable historian. Native source selection is
not a CLI argument and there is no fallback to fixtures. No current attempts ->
explicit failure, even if historical executions remain on disk. Run serially.

The published first/restored reports each recorded 9 attempts/task links,
1 matching live process and 8 unknown process observations. Main/schema hashes
were unchanged. Native history was truncated (`native_complete=false`), runtime
coverage partial, atomic runtime watermark absent and role availability unknown.
The second one-shot run reopened the historian, invalidated old active freshness,
advanced the durable stream sequence and retained `reconcile_required=true`.
No native writer was stopped; WAL/SHM reader coordination is excluded from the
main-file/schema invariant, as in the parent work observer.

## A25: what was and was not exercised

The actual proof utility exits naturally after each observation. Restart restores
observation without stopping, controlling or replacing any native execution.

Uninstalling a shared live installation or modifying native schedules would be
unsafe and outside the sole approved board scope. The A25 test therefore uses:

1. Synthetic native board rows and a separate synthetic schedule file outside a
   disposable Workshop deployment.
2. A real independent silent OS child, owned ONLY by the test harness, recorded
   with its actual verified spawn fingerprint in the native fixture.
3. Real source-only install (`scripts/dev.py install`), subprocess observation,
   normal observer exit, removal of ONLY that copied Workshop deployment,
   restoration/reinstallation and renewed observation into the retained historian.
4. The child remains alive; native DB/schema and native schedule bytes remain
   unchanged at every step. No observer sees the schedule path or process-control
   handle. Only the test closes its own child's stdin during final cleanup.

This is actual install/stop/uninstall/restore of an isolated source deployment
against synthetic native stores, NOT a claim that shared live Hermes was
uninstalled or that live schedule stores were accessed/validated.

## Verification and remaining scope

See `evidence/HERMES_RUNTIME_REVIEW.md` for red/green commands, exact cases,
actual-vs-fixture distinctions and clean-checkout evidence. The source-only
install exposes `workshop_collectors.hermes_runtime` without packages, pip,
network or new dependencies. Existing demo/test/check commands remain synthetic.

No outbox, daemon, renderer, HTTP/SSE/binary OTLP listener, production deployment,
fleet-health, full Phase 2 gate, or MVP acceptance is included. The already-created
Phase 2 gate card owns outbox + workflow integration and the full closing gate;
Core retains independent review and merge authority.
