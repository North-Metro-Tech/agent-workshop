# Hermes work observer (Phase 2 slice 1)

This is a local read-only collector library and opt-in one-shot acquisition,
not a monitoring daemon, frontend, durable ingestion pipeline or Phase 2 gate.

## Source authority and scope

`approved_scope()` is the only approved live factory. It binds the literal board
`agent-workshop` to `/home/aaron/.hermes/kanban/boards/agent-workshop/kanban.db`,
source instance `local-hermes-agent-workshop`, and profiles `coder` and
`vitruvius-core`. It refuses path/board overrides, symlink resolution to another
path, and environment/current-board fallback. Legacy `~/.hermes/kanban.db`, other
boards and HTTP helpers are excluded. Generic `SourceScope` construction is
trusted local adapter configuration for synthetic fixtures or a separately
approved future adapter, not a producer-facing scope-selection API.

Importing does not acquire anything. Fixture tests create only synthetic stores.
No native helper is imported: even Kanban GET helpers can call `init_db()`.
No hooks are installed and no gateway, provider, profile or native config changes
are required. No new dependency was added. Ordinary execution used the authorised
direct fallback because Claude Code is absent from this environment.

## Atomic acquisition and bounds

Each `HermesWork.observe(board=..., acquired_at=...)` opens `mode=ro` with
`query_only=ON`, `trusted_schema=OFF`, a 100ms busy timeout and one
`BEGIN DEFERRED` transaction. All six exact ordered table schemas (including
hidden-column rejection) are checked in that read view. The board-local
`MAX(task_events.id)` and every record batch come from the same transaction.
Constants select tables/orderings; values/limits are parameters. No caller SQL
is accepted. Connections close on success and every failure.

Limits: 256 records per table plus one lookahead, 64 KiB per record, 1 MiB
aggregate across the six tables, and a 500,000-instruction SQLite VM budget.
Rows are consumed incrementally. Schema/encoding/size/VM/read failures publish
no partial result and do not refresh successful-acquisition time. Row truncation
returns a snapshot marked incomplete with the precise truncated table list.
A missing record in that snapshot is NOT a tombstone/deletion. Task/run identity
includes the trusted source instance and board. A collector detects a changed
file device/inode between successful observations or during a read and requires
explicit rebind. Local filesystem/configuration is trusted; this is not a claim
of defending hostile filesystem TOCTOU, inode reuse or in-place DB restoration.

The atomic watermark is a BOARD EVENT CURSOR, not a global database revision,
complete event history, cross-authority order or complete runtime inventory.
Some native changes (e.g. process sampling/heartbeats) need not be represented by
that cursor. No destructive reconciliation, replay guarantee, actor correlation
or historian integration is implemented here. Those contracts belong to the
next slices and must preserve their own epoch, coverage and loss semantics.

## Five semantic views

All views derive from that bounded source snapshot, not independent native
queries; callers get defensive copies.

- `board_view()`: explicit native station grouping, native ordering (done newest
  completion first), matching event watermark, source completeness. Unknown
  native status goes to `unknown`, never silently to `todo`.
- `task_detail(id)`: task fields, station, parent/child links, comments, events,
  attachment metadata and attempt history present in the bounded snapshot.
- `workers()`: open run rows with a PID and a task at `running`, just as the native
  selection; labelled `source_record`, never proof of a live process.
- `run(id)`: native attempt status/outcome, timestamps, PID and spawn identity.
- `inspect(id)`: unknown by default; optional matching process corroboration.
  No native inspect helper is called. Missing/denied/unavailable evidence stays
  unknown, never a fabricated failure or dead process.

This is NOT a wire-compatible replica of the HTTP dashboard. Age/now metrics,
config-derived diagnostics, warning synthesis, graph result/summary previews and
HTTP query-filter/pagination contracts are unsupported, rather than running
native helpers or guessing config. Snapshot `complete` concerns only bounded
source tables, not unsupported diagnostics or runtime coverage. Runtime coverage
is ALWAYS `partial`. Any truncation conservatively marks every derived view
incomplete; no filtered view may claim it recovered missing global rows.

Privacy: body/result/error/skills/comment text, raw event payload, run summary/
metadata/error, and attachment stored path are cleared before the result is
published. Their metadata rows remain present. Bounds apply BEFORE redaction.
Attachment contents, bodies referenced by @paths, raw arguments/results,
transcripts, environment and command lines are never followed, read or persisted.
Other native labels/filenames are data, not trusted UI markup or commands. A later
renderer must still escape them. No arbitrary JSON event payload is parsed here.

## A05: observation is not progress

`process_probe=None` returns unknown. A separately supplied trusted observer can
return `ProcessSample`; only exact PID plus native recorded boot/instantiation
and start-time fingerprint equality establishes process liveness. Legacy integer,
missing or `unverified` spawn identity cannot match. Mismatch/PID reuse,
unavailable metadata or access denied returns unknown, not a terminal event.
Zombie/dead process states are distinguishable only for matching identities.

The provided optional `linux_process_probe` uses standard-library reads of
`/proc/<pid>/stat`, `/proc/1/stat` and the kernel boot ID. It reads process stat
twice to reject incarnation changes during sampling. This replaces unsafe native
inspect semantics and needs no psutil: no missing psutil result is treated as
liveness. Non-Linux/missing/denied proc metadata stays unknown. These observations
occur AFTER closing the DB transaction; process state is not atomic with its
watermark and only corroborates a worker process, not a tool/turn/session actor.

Even a matching sleeping process yields `progress=unknown`,
`tool_activity=unsupported`, `failure=unknown`, `retry=not_requested`.
`on_session_end`/turn finalisation records never imply OS process death.
An ended run row can coexist with a still-live process; those facts stay separate.
The observer does not invent retries, signal workers, reclaim claims or accept
work. No liveness freshness is inferred from native occurrence timestamps.

`quality(now=...)` uses the existing acquisition-clock freshness function:
15 seconds stale, 30 disconnected, future acquisition unknown. A failed read
retains the last successful snapshot but reports disconnected; a successful
reacquisition restores observation. Caller clocks must be comparable. There is no
wall-clock read in collector/domain code. Do not present an old `inspect()`
result as currently live without applying snapshot age/collector quality.

## A06: attempt/process/task disposition are independent

`execution(id)` is a source-qualified work projection, NOT a reducer lifecycle
update. `ended_at` means the attempt exited according to native records. Native
blocked/review task disposition remains at that station regardless of attempt
exit or process liveness. Unsupported/missing disposition remains unknown.
Workshop-local alarm acknowledgement only touches Workshop-owned alarm state;
there is no collector acknowledgement or native task-control operation.

## Reproduce

Existing approved Python with pytest (no downloads):

    /home/aaron/hermes-agent/.venv/bin/python scripts/dev.py test
    python3 scripts/dev.py check

One-shot LIVE scope (explicit opt-in, no daemon or synthetic substitute):

    python3 scripts/observe_work.py --approved-local

The script prints hashes, counts, state labels and limitations only. It executes
all five semantic surfaces and checks the main DB byte hash and schema hash
before/after each observation. Existing native writers are NOT stopped; an
external checkpoint/change can invalidate this observational proof and fails the
command. Matching hashes prove only those measured intervals, not universal
absence of side effects or WAL/SHM changes. DML impossibility is separately
adversarially tested on synthetic copies (including query_only turned off while
mode=ro remains). No DML is attempted against the native store.

Observed live evidence is partial: `task_events` exceeds the 256-row bound. That
is reported, not hidden and not fixed with unbounded reads. No continuous live
blocked→review→exit sequence was forced or claimed. A05 silent-child/PID/turn
variants and A06 exit/acknowledgement are fixtures; the real silent OS child is
owned/stopped only by its test. Durable runtime integration, complete pagination,
outbox, stop/uninstall/restore and final approved-workflow acceptance remain in
the already-created downstream Phase 2 cards. There is no fleet/MVP claim.
