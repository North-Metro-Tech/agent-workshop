# Phase 2 slice 2 — Hermes runtime observer review handoff

Task: `t_bbfe861b`. Branch: `feat/phase2-hermes-runtime`.
Base slice: `f0b5811` (parent PR #5 now merged by Core into main `5f89fc8`).
Signed red baseline: `949646c`. Signed implementation: `791fe97`.
Later documentation/evidence-only commit records the clean-checkout proof.
Core owns independent approval and merge; this is implementation QA, not approval.

## Requirement and result

Build the explicitly scoped `hermes_runtime` observer, persist actual approved
native attempt/process correlation through existing A08/A10 ingress and historian,
and prove non-interference on stop/uninstall/restore (A25). No renderer, new
dependency, network listener, outbox, agent control or scope expansion.

Implemented a standard-library collector on the existing bounded native reader,
a dedicated trusted source/feed/role/runtime binding, versioned finite OTLP log
metadata, scoped task links and serial atomic historian publication. Canonical
lifecycle evidence now respects the binding rather than always asserting
runtime-observed evidence. Process corroboration does not promote it.

## Red -> green evidence

All commands use the already-approved pytest interpreter where pytest is needed:

```
/home/aaron/hermes-agent/.venv/bin/python -m pytest -q backend/tests/test_hermes_runtime.py
```

Before implementation (signed `949646c`): 29 failures, missing runtime collector.
Actual capture: `phase2-runtime-red.txt`. This is an API/behavior baseline, not a
claim that the then-nonexistent collector had 29 separately reproduced defects.

The first implementation then passed 48 focused cases. Read-only internal QA
found two substantive gaps. Tests added BEFORE their fixes demonstrated:

- Same native file replaced between observer/service restarts, recycled run/task
  IDs: did NOT reject identity replacement.
- No CURRENT native attempts after prior stored history: live-proof script did
  NOT fail and could wrongly label empty acquisition as actual proof.

`phase2-runtime-review-red.txt`: 2 failed, 1 passed, 30 deselected against that
intermediate working implementation. The passing third regression separately
confirms process change without any board event is still new durable evidence.
This intermediate capture is not represented as a separate signed commit.

Fixed with durable `(device, inode)` binding in the SAME transaction as
cursor/records (also fail closed on omitted/malformed/legacy-unproven identity),
and a current-acquisition requirement before opening the main proof historian.
Tests now pass. Source identity is trusted local configuration, not producer
metadata; old optional-field-free states still decode for original generic feeds.

Final captures (scenario selectors overlap and are NOT summed):

| Capture | Real command selector | Result |
| --- | --- | --- |
| `phase2-runtime-green.txt` | the three new runtime/edge/entrypoint test files | 59 passed |
| `phase2-runtime-full.txt` | `pytest -q` | 397 passed |
| `phase2-runtime-A08.txt` | `pytest -q -k A08` | 93 passed, 304 deselected |
| `phase2-runtime-A10.txt` | `pytest -q -k A10` | 66 passed, 331 deselected |
| `phase2-runtime-A25.txt` | `pytest -q -k A25` | 4 passed, 393 deselected |

Prior 338 tests remain green. `git diff --check` also passed. No type-check,
coverage percentage, benchmark, certification or external CI success is claimed.
Editor import diagnostics are not substituted for executed tests.

## A08/A10 evidence map

`backend/tests/test_hermes_runtime.py`, `test_hermes_runtime_edges.py`,
`test_runtime_entrypoint.py` cover:

- Actual adapter payload -> OTLP validation -> serial durable source-record
  execution/task/metadata correlation; detached snapshots, finite privacy schema.
- Matching native spawn vs reused PID, missing identity, denied sample, unsupported
  process state, zombie/dead samples: unknown/dead never fabricates terminal
  execution or progress. Silent behavior never requests retry.
- Ended attempt status/outcome mapping is independent of native task station,
  process state, review/blocked/acknowledgement; same native IDs across configured
  source instances/boards remain distinct.
- A10 composite allowlist for lifecycle AND metadata-only observations; empty or
  wrong scope rejects the entire durable batch; corrupt metadata also rolls back.
- Same packet retry dedups; changed observation with reused stream identity
  rejects; epoch retirement/cursor regression/reopen preserve their fences.
- Acquisition stays original and cannot gain freshness from delayed receipt.
- Board event cursor does not select stream identity, and unchanged event cursor
  cannot hide a changed process sample.
- Restart invalidates active freshness, retains identity/task/cursor/history and
  leaves reconciliation latched. Complete native/source-record evidence cannot
  clear it. Source replacement survives observer/service restart as a rejection.
- Bound source identity cannot be omitted, malformed, changed or silently added
  to prior unproven history; invalid ingress cannot persist identity/cursor facts.
- Current native acquisition, not retained history, is required for proof success;
  no live source is touched without explicit command opt-in.

Existing historian snapshot/event race, journal loss, replay/idempotence,
full/partial scope, unsupported mapping and source epoch tests remain green.
This collector does NOT have the atomic runtime evidence required to invoke
complete runtime recovery. Native snapshot completeness never manufactures it.

## Actual approved workflow — not fixtures

Executed twice, serially, with actual approved scope, no native writer stopped:

```
python3 scripts/observe_runtime.py --approved-local
```

Captures: `phase2-runtime-live-first.json`, `phase2-runtime-live-restored.json`.
Each persisted and read back 9 actual native attempts and 9 composite task links,
with 1 matching live process and 8 unknown process observations. Both source
main-file and schema hashes match before/after. Actual history was truncated,
so `native_complete=false`. Runtime coverage partial, atomic runtime watermark
null and role availability unknown are explicit in BOTH reports.

Each command also took the SAME actual snapshot through a deliberately empty
allowlist in a separate disposable Workshop historian: rejected, unchanged
projection/revision, and no persisted cursor, source identity or execution.
The native source path was NOT changed to construct this negative-policy case.

The second command reopens the persisted historian: startup active freshness
invalidated, stream sequence advanced from 1 to 2, correlations retained and
reconciliation STILL required. Matching process metadata does not clear it.
The main file/schema invariant excludes native WAL/SHM read coordination and
concurrent native writers; those were not stopped. Reports contain only counts,
reviewed labels and hashes, not raw native rows, PIDs, fingerprints or payloads.
The private historian is git-ignored under `.workshop-state/`, not published.

## A25 actual-vs-fixture boundary

The actual observer is a one-shot process which exits normally and can be
restarted to re-establish observation without controlling native agents. No
shared live Workshop/Hermes installation was removed and no live native schedule
store was read or modified. Those actions exceed this sole-board approval.

The isolated A25 regression executes REAL source-only install, observer subprocess
exit, removal of ONLY a copied Workshop deployment, restore/reinstall and
re-observation into a retained historian. Native task rows and a separate native
schedule file are SYNTHETIC and live outside that disposable deployment. A REAL
independent silent child remains alive throughout, and native DB/schema hashes
plus schedule bytes stay identical at every step. Test cleanup alone owns the
child's stdin; observer code receives no control handle or schedule path.

The collector public-surface/AST checks retain no native mutation/control APIs.
The existing allowlist test was extended only for the required Workshop
reducer/ingest/historian imports, not new network/process-control modules.

## Clean-checkout installation and development evidence

`phase2-runtime-clean-checkout.txt` is actual output from an archive of signed
implementation `791fe97916429954a54586cf51c1c150a35959c5` into a fresh
Workshop-owned, git-ignored directory. PYTHONPATH was explicitly unset:

1. `python3 scripts/dev.py install` -> source-only no-pip venv; no downloads.
2. `.venv/bin/python -m workshop_collectors.hermes_runtime` -> import-only module
   executes successfully with zero source acquisition.
3. Approved pytest interpreter `scripts/dev.py test` -> 397 passed.
4. `python3 scripts/dev.py demo` -> explicit synthetic projection.
5. `.venv/bin/python -m workshop.demo` -> same supported synthetic entrypoint.
6. `python3 scripts/dev.py check` -> compile backend/collectors/scripts succeeds.

A preliminary inline `python -c` import command was refused by headless command
policy before execution. No permissions/configuration were changed; the normal
import-only `-m` module invocation above is the tested supported alternative.
No package was installed, added or bumped, so no quarantine exception was needed.

## Review attention and remaining limits

- Inspect `Ingest._corroboration` and both binding-evidence lifecycle call sites;
  no source-record observation may become runtime lifecycle authority.
- Inspect atomic source-identity/cursor rollback, old codec compatibility and
  immutable replacement semantics. Device/inode assumes trusted filesystem;
  hostile races/inode reuse/in-place restore are not solved.
- Preserve dedicated scope, original comparable acquisition clocks, stable
  collector epoch/sequence and separate native cursor domains in the next outbox.
- Do not treat namespaced attempt context as an observed Hermes session, historical
  process attrs as current process API, or role availability as fleet health.
- `RuntimeSnapshot.atomic_watermark=None` is an evidence limit, NOT missing code
  to fill from the native event cursor. True complete runtime recovery requires
  a different supported atomic source.
- No daemon, outbox, network service, renderer, production release, full Phase 2
  acceptance or MVP-readiness claim. Existing child `t_f11a8ea8` owns outbox + full
  workflow gate; `t_7e8a8223` remains the sole MVP notification gate.
- `RESUME.md` is the shared Core/coder hotspot; one serialized additive handoff
  preserves historical/Core text. Core independently reviews and merges the PR.

Implementation used the already-authorised ordinary direct fallback: Claude Code
was absent from PATH and checked standard executable locations. No harness,
provider, credential, dependency or permission workaround was attempted. A
read-only internal review subagent supplied findings; neither that QA nor the
implementer's test run is substituted for Core's independent approval.
