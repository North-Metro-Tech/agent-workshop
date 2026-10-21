# Phase 2 gate: implementation review handoff

Task `t_f11a8ea8`, branch `feat/phase2-workflow-gate`, base `main`.
Implementation `fe6467f36d5812d38b5954c2552f817be60ede12`; test-first baseline
`dbaa890551926864876e2c58a452295c220fd12f`. Accepted PR #6/main `d336ea6` was
incorporated with signed merge `b9bbc7d`. Core owns independent review/merge;
this evidence is developer QA, NOT independent approval or MVP readiness.

Claude Code was absent from PATH and the standard executable locations. Work
used the previously authorised direct fallback, not an installed replacement,
provider/model workaround or new dependency. No external packages were added.

## Requested / delivered

- Bounded Workshop-owned `outbox.py`, FIFO at-least-once serial delivery through
  existing `Storage.otlp`, stable cursors/epoch/source identity, original
  acquisition retained, backpressure without eviction, crash-before-ack retry.
- Integrated approved local native work/runtime observation -> outbox -> existing
  validator -> historian -> reducer -> API projection; no alternate wire envelope,
  renderer, listener, daemon, native helpers or native-write enable route.
- Independent source-label/lifecycle and immutable-acquisition comparisons, not
  just equality with the adapter's own mapping or historical record presence.
- Deterministic plainly synthetic collector demo, source-only install, explicit
  live opt-in, clean-checkout full-suite evidence and named A05/A06/A08/A10/A25
  artifacts. Shared/Core RESUME edits are preserved under one additive update.

## Execution evidence

Original parent suite: 397 passed. Closing focused suite:

    /home/aaron/hermes-agent/.venv/bin/python scripts/dev.py test backend/tests/test_outbox.py backend/tests/test_phase2_gate.py -q

35 passed (`phase2-gate-green.txt`). Full repository suite: 432 passed in 9.99s
(`phase2-gate-full.txt`). No prior tests removed or disabled. Existing structural
import fence grants ONLY `uuid` to `outbox.py` and ONLY `tempfile` to synthetic
`demo.py`; the broad import-fence advisory is not used as an excuse to permit
agent-control/network imports. Extra closing surface/API/import tests also pass.

`phase2-gate-clean-checkout.txt` records a real git archive of exact implementation
`fe6467f`, with inherited PYTHONPATH/VIRTUAL_ENV/CONDA_PREFIX removed. Executed
source-only no-pip install, old synthetic demo, new collector demo, installed
module collector demo, all 432 tests (11.13s), compile check and explicit-live
opt-out (expected exit 2). Both collector-demo entrypoints produced byte-equal
JSON; normal commands created no live observation state. Python 3.14 runtime and
existing approved Python 3.11/pytest test interpreter exercised without package
installation. The archive predates documentation-only final handoff updates.

`git diff --check` and compile checks passed. No type-check, coverage percentage,
benchmark, physical-disk cap, conformance certification or external CI-success
claim. Check exact published head/CI independently in the PR.

### Red/green record and QA fixes

- Signed baseline `dbaa890`: `phase2-gate-outbox-red.txt`, 18 expected failures
  before outbox implementation (`ModuleNotFoundError`).
- `phase2-gate-review-red.txt`: 6 failed / 29 passed before adversarial fixes,
  including one nested clean-command failure caused by the same queue defects.
  Retiring the queue epoch with an adjacent numeric historian cursor previously
  could acknowledge/drop a stale delivery; now checked before ingest. Empty
  snapshots previously consumed cursors; now rejected without mutation. An
  undelivered later acquisition with unchanged visible facts could pass the proof;
  now stable record identity binds original acquisition/epoch/cursor/execution.
  Incorrect adapter status/outcome labels previously compared equal to themselves;
  now independently checked against the acquired finite native vocabulary.
- `phase2-gate-green.txt`: all 35 focused cases pass after those fixes. Added a
  commit-before-ack regression reopening BOTH queue and historian handles.

## Gate map: actual approved source versus isolated variants

Named files contain the test names, not fabricated expected output. Counts below
are overlapping pytest `-k` selections and MUST NOT be summed as distinct tests.

A05: `phase2-gate-A05.txt`, 13 passed.
  New `test_A05_full_workflow_actual_silent_child_never_implies_progress` plus
  inherited PID reuse, unavailable probe, silent process, disconnect and turn-end
  cases. Real OS silent children are used against synthetic native stores; they
  are not a live Hermes tool-run fixture. Actual board proof compares acquired
  process corroboration independently of source lifecycle. Progress unknown,
  tool activity unsupported, retry not_requested; no silence=>failure inference.

A06: `phase2-gate-A06.txt`, 5 passed.
  New `test_A06_full_workflow_attempt_exit_station_and_local_ack_independent`
  covers blocked/review through the WHOLE delivery path and local alarm ack.
  Ended attempt, alive process and native task disposition remain independent.
  Actual source stations/attempt labels are compared read-only; no blocked/review
  transition or live local-ack injection was forced.

A08: `phase2-gate-A08.txt`, 105 passed.
  Includes original historian/recovery contracts, scoped runtime cases, bounded
  queue/offline FIFO/restart, regression and identity fences, commit-before-ack
  retry, retired epoch, empty acquisition and new full-path stop/restore proof.
  Queue/historian cursor and nonretired epoch must agree; no silent rebase.
  Actual approved workflow is delivered and reopened/reobserved with durable
  agreement. Crash/offline/overflow variants remain isolated. Reconciliation is
  deliberately latched: partial source-record evidence is not a complete
  runtime snapshot or recovery watermark.

A10: `phase2-gate-A10.txt`, 70 passed.
  Includes native-write interlock, scoped correlation, ownership/schema/path
  rejection and queued same-data empty-scope denial without ack/cursor mutation.
  Actual live data is ALSO rejected by an empty task scope using a disposable
  Workshop historian (`task_scope_denial`); the native main/schema hashes stay
  equal. Native DML attacks are tested on synthetic stores only.

A25: `phase2-gate-A25.txt`, 5 passed.
  New `test_A25_full_workflow_uninstall_restore_retains_pending_outbox_native_independent`
  actually installs/removes/restores an isolated source deployment with pending
  outbox retained outside the installation, then drains it through the historian.
  A real independent silent OS child and synthetic native tasks/schedules stay
  unchanged/alive; only test teardown terminates the child. Existing runtime
  isolated removal/restore and public no-control tests also pass. Shared live
  installation removal and live native-schedule access were NOT performed.

### Actual approved workflow evidence

`phase2-gate-live-restored.json` and `phase2-gate-live-reobserved.json` are serial
actual `python3 scripts/observe_workflow.py --approved-local` runs after the QA
fixes, not mocked test reports. Only the exact approved `agent-workshop` board,
source instance `local-hermes-agent-workshop`, coder/vitruvius-core profiles.

Both compare 10 acquired native attempts/task keys to mapped observations,
retained record metadata, durable reducer lifecycle/correlation and API output.
Immutable acquisition identity verified; same outbox epoch, source cursors 4 then
5, zero pending after delivery. Final run reports 5 observations accepted by
lifecycle ingest; the comparison count is not an accepted-transition count or a
claim that ignored terminal facts were applied again. The native running worker
is corroborated alive while progress remains unknown.

Both report nonempty scoped observation, unchanged native main/schema hash pairs,
actual same-data empty-scope denial with historian unchanged, reopened historian,
startup freshness invalidation, reconcile_required=true, runtime_coverage=partial,
role_availability=unknown and native_write_enabled=false. Task event history is
truncated; the board cursor is NOT the collector cursor or an atomic runtime
watermark. Each JSON contains per-scenario actual-versus-isolated labels.

`phase2-gate-live-pre-review.json` is a historical first run BEFORE the strengthened
acquisition proof; retained for transparency, NOT the final acceptance evidence.
Native hashes cover measured intervals/main/schema only, not WAL/SHM coordination
or a promise that concurrent native writers cannot run.

## Review focus and remaining boundaries

Read `docs/phase2-workflow.md` for precise recovery/ownership/budget contracts.
Important review targets: outbox commit/ack separation and epoch/cursor fences,
original acquisition identity, comparison independence, empty-scope denial,
source-record authority, and fixture/live labels. No native DB initialization,
profile/config writes, dependency installs or schedule/control calls were added.

One serial collector/historian writer; trusted local configuration/filesystem;
exact absolute nonsymlink queue path. No hostile hardlink/TOCTOU, inode reuse,
malicious DB, backup restore, clock rebasing, automatic schema migration or
multiwriter guarantee. Configuration/clock/source changes fail closed for
explicit recovery. Queue bounds are 64 pending batches, 4 MiB pending payload,
1 MiB request with existing ingress record limits, NOT total file/WAL/historian/
audit/domain/dedup storage caps. Overflow rejects no-drop; caller must report
anything it elects not to retry. No continuous transition-capture/replay claim.

No renderer, HTTP service, live native control, global fleet health, full runtime
availability or MVP readiness. Phase 3/deployment and the final MVP release
checks already belong to downstream `t_7e8a8223`; this card does not do that work.
Core reviews and merges this PR before Phase 2 is accepted. Implementation task
completion releases the existing graph only; no duplicate same-card review,
auto-merge, new review task or owner-ready notification is issued.
