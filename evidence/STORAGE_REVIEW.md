# A08 storage/recovery evidence and review handoff

## Requested and delivered

Durable Workshop-owned SQLite WAL historian, initial migration, atomic source
snapshot/replay recovery and durable alarm occurrences/audit on merged PR #2
(base `ddbf893dddd27af39d041f486b76d64cabbd3591`). Synthetic fixtures only.
No native database acquisition, renderer, live integration, HTTP listener,
new dependencies, provider/profile changes or runtime-write path.

- `backend/workshop/storage.py`: closed-type JSON persistence for reducer state,
  execution provenance/conflicts, roles/signals/coverage, feeds, correlations,
  ambiguities, alarm rules/controls/occurrences/audit and internal sequencing,
  ingress identity/order/epoch/retired-epoch indexes, source cursors/generations.
- `backend/workshop/migrations/001_initial.sql`: explicit Workshop ownership,
  schema version, domain tables, revision checkpoints/journal and snapshot jobs.
  WAL with FULL synchronous durability, atomic writer transactions and rollback.
- Durable CE/OTLP entrypoints retain only bounded validated/redacted batches.
  Ingest's small `_last_batch`/`_last_effects` handoff identifies effective
  observations for watermark merge; no input bytes/content are saved.
- Manifest/generation/scope/epoch/watermark snapshot assembly, no domain mutation
  until all pages arrive, safe replacement of current membership only for full
  runtime-observed supported inventory; partial/unsupported/weak evidence never
  deletes unseen execution objects or establishes authoritative availability.
- History-preserving snapshot/journal merge above the trusted source watermark,
  protected newer fields, retained terminal/conflict provenance and explicit
  identity discrepancies even on protected cross-role canonical keys.
- Startup invalidates live freshness and complete coverage and discards pending
  snapshots, while keeping histories, source epochs/dedup/order and alarm audit.
  A complete snapshot clears only its own latch; signals must be reacquired.
- Atomic projection + service cursor read view; bounded resumable checkpoints;
  malformed/foreign/future/expired cursors request one fresh snapshot.
- `LocalAPI(storage=...)` acknowledges alarms durably without changing authorization
  or source conditions; `LocalAPI(reducer)` remains an in-memory fixture facade.

## Actual execution evidence

Existing Python 3.11.15 / pytest 9.1.1 environment, no installs. The default
Python 3.14.7 has no pytest; that does not justify a dependency installation.

1. Original full suite, before changes: `182 passed in 0.16s`.
2. SSH-signed executable red baseline `efdc87278cbad6b9b1af9c2c0dad37902c78980f`:
   tests first, constructor stub raising NotImplementedError, actual result
   `1 failed, 33 errors in 0.31s`, exit 1. The 33 are fixture setup errors from
   that stub, not represented as assertion failures. `a08-red.txt` preserves
   the full output and exit footer. The final module replaces the entire stub.
3. Initial implementation: all 34 initial A08 cases green.
4. Adversarial production QA found history rewind, partial deletion/freshness,
   weak inventory authority and cross-source conflict defects. Added regression
   assertions BEFORE fixing them: `9 failed, 4 passed in 0.43s`, exit 1,
   `a08-edge-red.txt`. Replaced baseline restoration with history-preserving
   current-state/watermark merge; no terminal/disputed observations are erased.
5. Second QA found protected newer cross-role canonical keys could suppress the
   snapshot identity conflict. Added failing assertion first:
   `1 failed, 17 deselected in 0.08s`, exit 1,
   `a08-correlation-red.txt`. Fixed by recording reducer discrepancies while
   protecting newer lifecycle fields, and retaining nonconflicting snapshot
   observations as provenance rather than double-applying them.
6. Final full suite: `234 passed in 1.36s`, exit 0, `a08-green.txt`.
   Includes the original 182 cases. Separate storage-only execution:
   `52 passed in 1.22s`, exit 0.
7. `python -m compileall -q backend` passed under Python 3.11.15 and 3.14.7.
   `git diff --check` passed. `.gitattributes` already preserves raw red-output
   whitespace; captured failure output is not reformatted.

These are real captures, not fabricated output. The additional QA agents were
read-only engineering advisories, not independent Core review or approval.
No type-check, coverage-percentage, benchmark, frontend, external CI, binary
OTLP, HTTP or live operational acceptance result is claimed.

## Acceptance mapping and fault injection

`backend/tests/test_storage.py` and `test_storage_edges.py` name A08 cases for:

- Missing terminal repaired from a complete source snapshot, immutable terminal
  history even when omitted and already observed at/below the watermark.
- Service restart, exact identity retry and changed-content rejection across
  reopen, persisted source ordering and redaction before disk retention.
- Partial/scope-limited/unsupported responses, partial freshness after restart,
  manifested multi-page commit, identical page retries and invalid generations,
  pages, scope, clocks, duplicate identities and watermarks.
- Newer start and terminal events racing with snapshot pages; ignored obsolete
  revisions do not shadow repair; newer active fields are not overwritten by
  an older terminal snapshot; cross-source conflicts and cross-role alias
  identity discrepancies survive merge.
- Epoch change while collecting pages, incomplete pages discarded on service
  restart, regressive record revisions and expired snapshot replay windows.
- Browser-style resume, empty current replay, bounded history expiry and
  malformed/foreign cursors, snapshot projection and cursor from the same WAL
  read view while another connection commits a real racing event.
- Domain exceptions, unsupported serialization, SQL abort triggers during
  execution writes and snapshot revision commit: no state/cursor/identity
  publication on failure; snapshot pages remain available for a safe retry.
- Actual child process `os._exit(0)` after a committed terminal ingest, without
  connection cleanup; reopen recovers the committed WAL fact and identity.
- Alarm occurrence/control/current pointers, pending delays, incident numbering,
  cleared/acknowledged identity and audit through reopen; durable authorized
  local acknowledgement does not clear the source condition.
- Correlations, ambiguities, task keys and discrepancies round-trip as domain
  types; detached read mutation cannot modify durable state.
- Foreign/native-shaped synthetic SQLite file rejected without changing a byte.

Every DB is a pytest temporary fixture. No real actor/native data is opened.

## Standards correction

Per Core's explicit routing note, `docs/standards.lock` now resolves unchanged
GenAI SHA `547934afa90a34298441caf80c43b27255c3a292` in
`open-telemetry/semantic-conventions-genai`, which Core verified via GitHub API
HTTP 200 on 21 October (commit dated 18 October 2026, “run conformance in strict
mode, fix or declare violations (#444)”). Earlier HTTP 422 queried the wrong
repository. Development stability and no upstream-conformance claim remain.
This is reference metadata correction, not dependency adoption or installation.
Earlier historical evidence files are preserved verbatim rather than rewritten.

## Review attention and limitations

Read `docs/storage.md` for exact API and trust contracts. In particular:

- The adapter supplies a real atomic source snapshot/watermark and a stable
  monotonic source sequence independent of execution revisions and service
  projection cursors. Producer CE extensions are not trusted cursor inputs.
  Native sequence reset/gap translation belongs to the adapter. Sparse cursor
  jumps alone do not prove a missing observation.
- One service writer, serial calls, local filesystem, dedicated role/source/feed
  owner. Opening an existing historian is STARTUP and invalidates live state;
  it is not a passive second-reader constructor. Short SQL transactions do not
  wait on UI/network operations. Caller clock values must remain comparable
  for persisted alarm deadlines.
- A local/config/alarm mutation during source snapshot collection conservatively
  requests a new snapshot instead of replaying arbitrary callbacks or risking
  loss. An expired window similarly requests reacquisition, never partial commit.
- Retention bounds the revision/checkpoint journal (default 128) and snapshot
  page buffers. Domain histories, audit and dedup/order indexes are retained,
  not pruned. Full-state revision checkpoints and domain-table replacement writes
  favour correctness over demonstrated fleet-scale throughput. No whole-database
  byte/time quota, archival policy, collector outbox or online-backup command is
  claimed. Do not prune dedup independently of source replay semantics.
- No concurrent worker queue, native SQLite reader, HTTP/SSE/browser binding,
  auth/CSRF implementation, binary OTLP codec, renderer, demo or A10 completion.
  These boundaries are explicit rather than hidden behind synthetic green tests.

## Handoff

Feature branch `feat/a08-durable-recovery`, target `main`. Core independently
reviews and merges under the owner's authorisation; implementer does not
self-approve, enable auto-merge or merge. Exact published PR/head and signature,
whitespace and external-check evidence are supplied on the board handoff after
publication/read-back. RESUME carries objective/last decision/next action/open
question. Hotspot: `RESUME.md` — shared Core/coder handoff, serialized edit.

Claude Code was absent from PATH and standard install locations, so the Lead
used the authorised direct-implementation fallback. No install or provider/
model/profile/credential workaround was used. Existing downstream A10 and MVP
QA/release children mean task completion releases the implementation graph; it
is not independent approval or a claim that the product MVP is ready.
