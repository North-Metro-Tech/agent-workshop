# Phase 2 workflow and bounded outbox

This closing slice joins the existing approved `hermes_work` and `hermes_runtime`
read-only observers to the existing OTLP ingest/historian/projection path. It is a
library plus explicit one-shot commands, not a daemon, network service or renderer.
Core review/merge is the Phase 2 acceptance decision; there is no fleet-health or
MVP-readiness claim.

## Runnable commands

Python 3.11+ standard library only for runtime. An existing approved Python with
pytest is required for tests; no command downloads dependencies.

    python3 scripts/dev.py install
    python3 scripts/dev.py collector-demo
    .venv/bin/python -m workshop_collectors.demo
    /home/aaron/hermes-agent/.venv/bin/python scripts/dev.py test
    python3 scripts/dev.py check
    git diff --check

The two collector demo entrypoints emit equal deterministic JSON. They create
only temporary synthetic native/outbox/historian files. Process samples are
synthetic and labelled as such. Generated opaque stream identity is omitted from
output, not replaced by a fictitious identity. Original acquisition is 10,
delivery is 100; receipt does not make the observation fresh. Three synthetic
attempts demonstrate running, blocked and review task stations; ended attempts
can coexist with live process corroboration and non-accepted tasks. The demo is
not an observation of the host or a running Hermes actor.

The existing Phase 1 `demo` command and all earlier tests remain supported.

Only this command reads the real approved source (run serially):

    python3 scripts/observe_workflow.py --approved-local

No argument, environment variable, current-board selection or default path can
implicitly authorise live reads. `approved_scope()` still binds only the exact
`agent-workshop` board and coder/vitruvius-core profiles described in
`hermes-work.md`. Native acquisition and optional proc metadata use the existing
bounded read-only adapters. No helpers that initialise/migrate the native DB are
called. No schedules, command lines, environment, transcripts or attachment
contents are read.

## Delivery contract

`Outbox(path, binding=..., clock_id=...)` accepts trusted `RuntimeSnapshot`s only.
Its file is Workshop-owned and distinct from the native DB AND historian. A
foreign/native/historian file or a nonsymlink-path/configuration mismatch is
rejected before journal/data mutations. Local files/configuration are trusted;
this is not hostile-DB, hostile-filesystem, hardlink/inode-reuse, encryption,
secure-erasure or backup-restore protection.

One serial writer; no concurrent collector, historian writers or delivery calls.
No background retries, locks spanning native acquisition, sleeps or clock reads
exist in domain/collector code. Orchestration supplies monotonic acquisition and
receipt values and the host boot ID as the clock identity. Filesystem temp paths
respect the caller's TMPDIR. Native source identity remains device/inode based.

The outbox uses SQLite WAL + FULL synchronous, an application/schema ownership
guard, and these hard configuration ceilings:

- 64 pending acquisition batches (configurable downward).
- 4 MiB aggregate pending payload bytes (configurable downward).
- 1 MiB per serialized OTLP request; ingress still enforces its 256 records,
  per-record and schema/privacy limits.
- Fixed, bounded configuration/metadata; one pending head read at a time.

These are LOGICAL pending-payload bounds, not physical database/WAL size caps.
SQLite freelists, journals, temporary allocations and the separate retained
historian/domain/audit/dedup history are not claimed bounded by that 4 MiB.

Enqueue atomically persists a positive stream cursor, original acquisition,
source file identity, serialized safe payload, and incremented next cursor. The
queue's epoch is generated once and survives reopen. Empty acquisitions are
rejected, not treated as an authoritative empty inventory. Acquisition regression
or changed source identity fails closed. A full queue raises `OutboxFull` without
eviction, cursor consumption or other data mutation. The caller must stop/drain
or retry/report missed acquisition; it must not interpret rejection as successful
capture. There is no silent drop counter, automatic snapshot or complete replay
claim. Observations missed while stopped are not reconstructed.

Delivery calls the existing `Storage.otlp` validator with the original acquisition
and current receipt time, stable epoch/cursor and original source identity. It
then acknowledges the queue entry. A crash before acknowledgement retains the
head; replay uses identical record IDs and payload. Historian commit and queue
ack are separate transactions: delivery is at-least-once, NOT a distributed
exactly-once transaction. Existing ingest deduplication makes repeated facts
idempotent. Cursor adjacency and matching nonretired stream epoch are checked
BEFORE ingest; foreign/advanced/regressed cursors or a retired/divergent epoch
cannot silently skip queued data.

Queued record IDs use a versioned internal tuple containing epoch, cursor,
original acquisition, and execution ID. This uses the existing approved
`workshop.record.id` attribute, not an extra wire envelope/attribute. It proves
which acquisition was delivered even when restart reconciliation intentionally
sets effective freshness to unknown.

## Recovery and removal

Persist the outbox and historian together, outside any disposable installation.
The command uses git-ignored `.workshop-state/workflow-outbox.db` and
`workflow-historian.db`. Reopening the historian invalidates live freshness and
complete coverage. Draining queued observations cannot clear that latch: this
adapter has source-record lifecycle authority, not a complete runtime inventory
or atomic runtime watermark. Process metadata may be reobserved while runtime
availability remains unknown. Ordinary ingestion's stale/ignored lifecycle
updates remain governed by the established ingest contract; acknowledging a
queued delivery is not native task acceptance.

On boot/clock/configuration/source-identity change, the outbox refuses automatic
adoption/rebasing, even if it is empty. Preserve old files as historical evidence;
resolve the approved binding/clock/reacquisition policy before creating a new
stream and compatible historian. There is no automatic migration, timestamp
rebasing, cross-boot freshness assertion, destructive rebind or restore command
in this slice. Restoring a mismatched queue/historian pair fails closed. Do not
point a new queue at arbitrary pre-existing history or delete a queue to restart
its cursor against a retained historian.

The one-shot process naturally exits. No runtime hooks/services/native routes
were installed, so there is no Workshop stop action controlling native actors.
A25 removes and restores ONLY an isolated copied installation, while retaining
its separate outbox/historian and a real independent silent child plus synthetic
native task/schedule files. Shared live installation removal and native schedule
access are not approved here and were not performed.

## Gate evidence and limits

`verify_agreement` compares the SAME acquired redacted native rows, mapped
observations, durable execution/task keys, retained finite process/station
metadata, and API projection. It independently maps native lifecycle and closed
status/outcome labels, checks immutable acquisition/epoch/cursor identity, and
rejects an undelivered later acquisition even if its visible facts are unchanged.
It does not requery the source or resample processes during comparison.

Every accepted comparison keeps runtime coverage partial and role availability
unknown. Board event cursor is diagnostic, not a stream cursor or atomic runtime
watermark. Source table truncation is reported, not promoted to deletion of
unseen records. Status/outcome report labels use the finite approved mapping;
unknown native values remain unknown. Main/schema hash equality covers each
measured interval only, excludes WAL/SHM reader coordination, and does not stop
concurrent native writers. A changed hash fails the live command.

Actual approved-board observations and isolated variants are deliberately
separate. A05 silence/PID reuse/turn-finalisation and A06 forced blocked/review/
local-acknowledgement variants are isolated tests, not forced live transitions.
A08 crash/overflow/offline variants and A10 adversarial DML are isolated too.
Per-scenario named output and actual same-acquisition/reopen readbacks are mapped
in `evidence/PHASE2_REVIEW.md`. Passing those tests is not continuous capture of
every transition, complete fleet coverage, an HTTP service, operational acceptance
or the downstream MVP gate.
