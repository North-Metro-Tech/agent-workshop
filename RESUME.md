# RESUME — Agent Workshop

## Latest implementation handoff — Phase 2 slice 2/3

Task `t_bbfe861b` implemented on `feat/phase2-hermes-runtime`, based on the exact
slice 1 head `f0b5811`; Core has now accepted/merged PR #5 (`main` merge
`5f89fc8`). Signed red baseline `949646c` (29 failures) and implementation
`791fe97`: 397 tests pass, including 59 new cases. Actual approved-board runs
persisted 9 attempt/task correlations, 1 matching live process and 8 unknown
processes; source main/schema hashes stayed unchanged, and empty task scope
rejected the SAME actual evidence without durable mutation. Restart invalidates
active freshness and leaves reconciliation latched. No atomic runtime watermark
exists for the native DB plus later proc reads; runtime coverage remains partial,
role availability unknown, lifecycle evidence source-record-only.

Internal QA found/fixed two red regressions: file identity lost across observer
restart (now durably bound atomically with cursor/records), and live-proof success
from old history when current acquisition had no attempts. A25 actually installs,
stops, uninstalls and restores a disposable source deployment with a real
independent silent child and unchanged synthetic task/schedule stores. Actual
live uninstall or schedule access was not attempted. Clean archive of `791fe97`
passed source-only install/runtime import/all 397 tests/both demos/compile checks
with PYTHONPATH unset; no external dependencies added.

Core independently reviews/merges this slice's PR (handle in task handoff).
Complete this implementation phase to release existing child `t_f11a8ea8`, NOT
same-card review or a review-required block. That child owns outbox/full workflow
and Phase 2 acceptance; `t_7e8a8223` remains the sole MVP notification gate. No
outbox, renderer, native control, full Phase 2 or MVP readiness is claimed here.
Evidence and caller contracts: `docs/hermes-runtime.md`,
`evidence/HERMES_RUNTIME_REVIEW.md`, `evidence/phase2-runtime-*`.

The earlier sections below are preserved historical/Core handoff context; this
latest section supersedes their slice-1-pending and slice-2-not-implemented state.

## Objective

Phase 1 of the read-only Workshop supervisory layer is COMPLETE and accepted: the
Phase 1 gate merged to main `364b669` at ~14:03 AEDT 21 Oct under the owner's
standing pre-authorisation. Phase 2 slice 1/3 is IMPLEMENTED on
`feat/phase2-hermes-work`, pending Core independent review/merge (PR handle in
the Kanban handoff). MVP gate `t_7e8a8223` remains the single owner
notification point; nothing here is an MVP-readiness claim.

## Last decision

Core independently reviewed and merged the Phase 1 gate (PR #4, branch
`feat/a10-phase1-gate`): 294 tests re-run at head `b9c0719` in isolated worktrees,
red baseline `735bfbe` reproduced (52 failed / 235 passed full-suite = 53 new
atop the 234 prior), all commits signature-valid, full diff and fences verified.
Base `59696e9` → main `364b669`, verified by read-back. Phase 1 closed: truth
model (A01–A04), wire semantics (A07/A09), durable historian (A08), scoped source
binding + bounded read-only SQLite primitive + fixed-off interlock + synthetic
demo (A10) — four PRs in one day, each independently reviewed before merge, suite
0 → 294.

Phase 2 routed per spec §17: `t_69111745` (collector base + `hermes_work`
observers, A05/A06) → `t_bbfe861b` (`hermes_runtime` observer + durable
correlation, A08/A10/A25) → `t_f11a8ea8` (Phase 2 gate: A05/A06/A08/A10/A25 on
the approved workflow, `outbox.py`, demo/dev commands). The MVP gate was
re-parented behind the Phase 2 gate; the board auto-demoted it `ready` → `todo`,
so the dispatcher cannot claim the owner notification point out of sequence.

## Next action

Core reviews the Phase 2 slice 1 PR — suite re-run, full diff, fences,
test-by-test acceptance mapping — then releases slice 2 on the accepted base.
Implementation completion releases the graph, not independent approval. Core
reviews each Phase 2 PR on handoff
and merges under the standing pre-authorisation. On Phase 2 gate merge, the MVP
gate becomes ready: that merge is the owner notification point (telegram-subscribed
card handles it; no separate Core message).

## Open question

Core resolved the initial acquisition conflict: direct `mode=ro`/`query_only`
SQLite, not native HTTP helpers (which call init_db). Sole approved source is
the `agent-workshop` board's exact native DB; profiles coder/vitruvius-core.
Slice 1 supplies six-table bounded atomic read snapshots with a matching
board-local event cursor, five semantic views, privacy clearing, optional
boot/PID/start-verified Linux process corroboration, explicit station/attempt/
process separation and acquisition freshness. 44 new cases pass; full suite
338 passed. Red evidence: 31 initial failures, then adversarial future-clock/
file-replacement failures fixed. All five actual read surfaces retained identical
main-file/schema hashes; actual event history is truncated and runtime coverage
is ALWAYS partial. Live transitions were not forced: A05 silent-child and A06
blocked/review/ack variants are fixture evidence, not full-workflow acceptance.
Details: docs/hermes-work.md and evidence/HERMES_WORK_REVIEW.md.

Remaining Phase 2 work is already routed: durable runtime correlation/ingress,
loss/recovery/epoch/replay semantics, outbox, complete approved-workflow gate and
A25 stop/uninstall/restore evidence. The board cursor is NOT a complete runtime
watermark or a database-wide revision. Operational watch:
coder handoff comments quote raw PR URLs by design, so the per-card respawn guard
may strand the next card after each Phase 2 merge — standing relay remedy applies
(check every ready card each pass; emit the operator handoff event; do not wait out
the 24h window).

Standing A08 contracts remain: serial service writer, dedicated configured
source/feed/role/runtime instance, comparable caller acquisition clocks, startup
freshness invalidation, complete supported runtime recovery only; replay
retention bounds checkpoints/journal, not domain/audit/dedup history. HTTP/SSE/
binary OTLP, durable runtime integration and renderer are outside Phase 2 slice 1/3. No type-check,
coverage percentage, benchmark, standards certification or external CI success
claim.

## Coordination

Cards owned by coder; Core reviews and merges under the owner's standing
pre-authorisation (reaffirmed 21 Oct). RESUME.md is the shared Core/coder hotspot:
serialized edits, preserve the other party's handoff. This copy travels with the
next PR per convention; the vault journal (operations-journal-2026-10-20.md,
21 Oct ~14:03 section) carries the full review record. Private specification and
owner directions are not published in the repository. No owner notification is
warranted until the MVP gate.
