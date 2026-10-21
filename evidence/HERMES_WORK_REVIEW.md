# Phase 2 slice 1 — engineering handoff (Core review required)

Base: merged Phase 1 main `364b669`. Branch: `feat/phase2-hermes-work`.
This is implementation evidence, not independent approval, Phase 2 acceptance,
fleet readiness or the MVP notification point.

## Requested / delivered

Build collector base + Hermes work observers with A05/A06 boundaries and native
read-only fences. Core explicitly amended acquisition to direct SQLite, excluding
all HTTP helpers because they initialise native DB state.

- `collectors/workshop_collectors/base.py`: explicit local scope, exact ordered
  schemas, hidden/view rejection, mode=ro/query_only, aggregate/row/value/VM
  bounds, one short deferred transaction and closure on every path.
- `hermes_work.py`: five bounded semantic views plus source-qualified work
  projection; board-local atomic event watermark; explicit unknown/truncation;
  privacy clearing; process identity corroboration; acquisition freshness.
- `scripts/observe_work.py`: opt-in one-shot LIVE proof, hashes/counts only.
- Source-only installation includes collectors; compile/test paths and the
  clean-copy regression were extended. No package installed or updated.
- Core's uncommitted post-Phase-1 RESUME handoff was preserved and serially
  updated once. RESUME.md remains a shared hotspot.

Claude Code was unavailable (PATH and standard executable locations checked).
The authorised ordinary direct fallback was used. No provider/config/credential
workaround, native helper import, hook install or process-control path was added.

## Test-first record

- Signed initial red baseline `3467bba`: 31 failing new tests, missing collector
  implementation. Raw output: `phase2-work-red.txt`.
- Initial collector + adversarial checkpoint `da5e800`: initial 31 green; edge
  tests then demonstrated 2 failures / 10 passes (future-clock freshness and
  same-path DB replacement). Raw output: `phase2-work-edge-red.txt`.
- Additional first-open replacement test failed on the intermediate code; raw
  capture `phase2-work-identity-red.txt`. Before/after-connect device/inode checks
  now reject the tested race. Trusted filesystem remains an explicit assumption;
  no hostile-filesystem or in-place-restore identity guarantee is claimed.
- Final focused collector suite: 44 passed (`phase2-work-green.txt`).
- Full suite: 338 passed (`phase2-work-full.txt`).
- Python 3.14 compile check and `git diff --check` passed. No external CI,
  type-check, coverage-percentage, performance or standards certification claim.

## Acceptance mapping

A05 — 12 named tests in `phase2-A05.txt`:

- Exact spawn PID + boot/instantiation/start identity required. Legacy integer,
  absent/unverified identity, mismatch and recycled PID never establish liveness.
- Matching silent sleeping process establishes process observation only; progress
  and failure remain unknown, tool activity unsupported, no retry requested.
- Test-owned real silent OS child is observed, remains live after a synthetic
  `on_session_end`, and is cleaned up by its own test. No native worker signalled.
- Unavailable/access-denied/failed probe is unknown, not dead/failed. Attempt exit
  does not imply process death. Acquisition failure retains old evidence without
  refreshing it; success recovers; stale/lost deadlines and future clocks tested.

A06 — 3 named tests in `phase2-A06.txt`:

- Exited attempt leaves native blocked/review task at that station, including a
  process still alive after disposition transition.
- Real Workshop-local alarm acknowledgement succeeds without altering fixture
  native main bytes/schema or task disposition. It never accepts work.
- Unsupported native disposition remains unknown, never accepted/coerced to todo.

Supporting A10/adversarial coverage:

- Each of five surfaces retains native main-file and schema hashes on fixtures.
  DML fails even after adversarial query_only=OFF because mode=ro remains.
- One WAL writer races a reader between watermark and task reads: old snapshot
  has old task+cursor; next acquisition sees new task+cursor. No mixed snapshot.
- Row truncation, aggregate/record limits, invalid BLOB/nonfinite data, wrong/
  hidden/view schema, VM instruction budget, profile scope, SQL-injection IDs,
  closed connections, exact URI and native-control import/surface fences tested.
- No environment/default-board discovery; explicit live opt-in required; source
  install/import/demo/test works without inherited PYTHONPATH in regression.

## Actual approved workflow evidence (not fixtures)

`phase2-work-live.json` is actual output from:

    python3 scripts/observe_work.py --approved-local

All five semantic surfaces acquired the approved agent-workshop DB with matching
before/after main-file SHA-256 and schema SHA-256 for each measured interval.
The source contains running and ended attempts, a matching live worker process,
blocked history and native task stations. This is one-shot observation, not a
continuous trace of every station transition. No native record was changed to
manufacture an acceptance scenario. The raw native bodies/payloads are not
published; report contains counts/labels/hashes and limitations only.

Important: source snapshot completeness is FALSE because task_events exceeds
256 rows. The snapshot says exactly which table truncated; runtime coverage is
ALWAYS partial. Missing bounded records cannot delete unseen actors. This cursor
is an atomic board-event position, NOT a global/native-database revision or a
complete runtime snapshot/replay watermark. Old attempts never become live from
receipt of historical records. Process metadata is sampled AFTER closing the
DB transaction, and only corroborates the native worker identity, not a tool,
turn or session actor. Native WAL/SHM reader coordination is not ruled out.

## Review focus and remaining scope

Inspect exact source binding, bounds/closure, snapshot/watermark race, unknown
handling, privacy, process identity and age semantics. `SourceScope` and optional
`process_probe` are trusted LOCAL configuration, not telemetry-controlled APIs.
The collector has no mutation/acknowledgement/control operation. Dashboard
config-derived diagnostics/age/filter conveniences are explicitly unsupported;
these are semantic read views, NOT an HTTP-wire-compatible dashboard replica.

Already-created child `t_bbfe861b` owns general hermes_runtime, real durable
correlation/ingress, A08/A10/A25. Child `t_f11a8ea8` owns outbox, full approved
workflow A05/A06/A08/A10/A25 gate and final commands/demo. They must not treat
this fixture-backed slice and partial one-shot live proof as fulfilled full
workflow acceptance. No outbox/renderer/listener/hook or new dependency here.

Implementation completion releases those pre-existing dependencies per the task
graph; Core still independently re-runs the gates and reviews/merges the PR.
No auto-merge, deployment, fleet-wide or MVP readiness claim.
