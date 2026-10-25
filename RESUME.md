# RESUME — Agent Workshop

## Root MVP recheck — owner PASS; new development-audit gate OPEN (25 October 2026)

Root `t_7e8a8223` rechecked the installed/Core-approved tailnet-origin merge
`5f7df84da20206a89d87a8ed692dff537edfefc4` in a new clean clone. Owner desktop
actual-use PASS is recorded by Core on `t_a87670b9` (25 October); do not ask for
that review again. Named-device enrolment and the authorised tailnet-only path
were accepted there. Live HTTPS and loopback both return 200; real Chromium on
the HTTPS path compares all 42 execution/task links, selects this root's actual
run 42, and matches exact durable schema2 revisions 92504/92505. Native controls
remain fixed off, coverage partial and availability unknown. Service remains
active/running, Restart=no, boot disabled, with no restart or deployment by this
root recheck. Canonical execution acquisition remains unknown after restart's
reconciliation latch; fresh HTTP transport must not be treated as fresh execution
proof. The original overstrict numeric-age QA failure is preserved separately.

Fresh exact-head results: 568 backend / 57 frontend / four actual synthetic TCP
Chromium tests, all zero-skip; typecheck/build/schema and clean-checkout demos
pass. Twelve named §16 transcripts remain committed at signed final-sweep
`df2ef871a6f45c1c82d65bb055ac500403fce80f` (d56e3ccf product), not relabelled as
fresh scenario runs at this newer head. Phase 3 independent audit and Core's
independent tailnet merge/delivery remain accepted upstream.

NEW BLOCKER: full development `sfw npm audit --include=dev` now reports one high
advisory, GHSA-834v-8h66-3h79 / CVE-2026-115895, on pinned happy-dom 21.0.1.
Production-only audit is clean; Happy DOM is a development test environment, not
a shipped application import. That distinction is not a silent audit waiver.
Patched 21.0.4 was published 20 October 2026 18:05:53.295 UTC and cannot clear
the seven-day quarantine until 28 October 2026 05:05:53.295 AEDT without an
explicit PO exception. No package/lock change, forced audit fix, age bypass,
untrusted-module exploit, or service/native-state mutation has been performed.
Core must disposition the development-only risk or route a quarantine-compliant
minimal remedy and independent verification before root completion.

Raw logs, JUnit, browser reports, registry metadata and failed attempts are in
`evidence/root-mvp-closure/`. This isolated local-only branch changes evidence and
this one additive RESUME entry only; every older section below is historical and
preserved verbatim. The installed checkout/OPERATOR/service remain untouched.
Do NOT send the owner-ready message or claim MVP completion from this checkpoint.
Owner first use occurred today, but the 30-day validation/write-up remains a
separate post-gate activity, not completed or self-certified here.

## Phase 3 F1–F3 remediation implementation — independent acceptance pending

Task `t_1503dfef`, branch `fix/phase3-service-history-annunciation`, based on
`ce52227c983598dcbb951f3c1d2ff55fe354ccdf`; PR base is `feat/phase3-mvp`, not
main. The recorded Core/PO minimal Uvicorn/runtime-transitive allowance now
exists. Exact hashed runtime lock, fourteen-resolution publication/hash/OSV
checks, Socket-wrapped installs and refreshed frontend quarantine/audit are
preserved under `evidence/phase3-remediation/`.

Actual loopback single-writer HTTP/SSE service, cookie login/CSRF/Host/Origin
boundary and Pydantic-generated TypeScript/JSON Schema are implemented. Timeline
now reads a bounded retained evidence excerpt, preserving provenance and unknown
historical acquisition times; alarm changes have a deduplicated polite live
region. README documents private secret provisioning and synthetic startup.
Approved-local collection remains explicit opt-in to the existing Phase 2 scope.
No real-fleet interaction or installation occurred in this remediation run.

Final local gates: 466 backend tests (including 34 service/CLI cases),
57 frontend tests, typecheck/build and schema reproducibility pass; actual
provisioned-browser suite runs all four tests with ZERO skips. It covers
canvas/DOM facts, reconnect, a new browser process, service restart/session
revocation/history retention and actual local acknowledgement. Raw earlier
failures are retained separately from final results. See
`evidence/phase3-remediation/REVIEW.md` for commands, mapping and limitations.
Manual screen-reader speech is NOT verified. Screenshot interpretation was
unavailable because the image-analysis provider rejected its API key; automated
real-browser pixel/DOM evidence is not a human visual review.

Next: independent review/merge of this remediation into `feat/phase3-mvp`, then
exact-head re-audit/Core approval (`t_86139b05`), twelve-scenario evidence rerun
(`t_4002229b`, PR #8 stays draft until rerun) and clean-checkout QA
(`t_f429ab51`, operator unblock still required). Their existing graph gates stay
in force. This is implementation completion only, not MVP readiness, permission
to deploy, auto-merge or an owner-ready notification. All earlier sections below
are preserved historical/Core handoff text. RESUME remains a serialized hotspot.

## Phase 3 intermediate checkpoint — NOT MVP ready

Task `t_7e8a8223`, branch `feat/phase3-mvp`, based on accepted main
`68e2367dd4b6552a9b0d6be9d33f56f35c211013` (Phase 2 PR #7 accepted/merged).
The frontend is implemented and independently exercised: 47 Vitest tests pass,
typecheck/build pass, full dev audit reports zero vulnerabilities. Existing
backend suite re-run: 432 pass. Exact approved frontend pins plus lock, all 99
resolution publication/integrity/tarball checks and Socket-wrapped ci evidence
are preserved. Pixel Agents visual-only adaptation is pinned/licensed, with
original stationary art and equivalent DOM. No live reads or installation.

This remains an intermediate checkpoint: no HTTP/SSE service or backend-generated
frontend schema, actual-service browser verification, full scenario acceptance,
independent review or release. The temporary TypeScript contract is marked as
such. See `docs/phase3-progress.md` for precise evidence, contract and remaining
work. Do NOT complete the sole owner-notification gate from frontend unit tests.

Before service adoption, Core/PO must explicitly allow a maintained minimal ASGI
server (`uvicorn`, no extras) and necessary audited runtime transitives, and
confirm runtime transitives of the already-selected FastAPI/Pydantic stack for
an exact Python lock. Current ruling covers the frontend toolchain; the host
harness's incidental installed server is not a reproducible product dependency
or authority to bypass the freeze. No packages outside the approved frontend
allowlist have been added/installed; no age exception requested. Resume service,
auth/SSE/security tests, Pydantic type generation, browser/final scenarios,
review and approved-scope installation only after that narrow ruling.

Claude Code remains absent; documented fallback used. Parent independently
reran the delegated frontend's gates. This entry is one serialized additive
hotspot edit; all prior Core/coder sections below are historical and preserved.

## Latest implementation handoff — Phase 2 closing gate

Task `t_f11a8ea8` implemented on `feat/phase2-workflow-gate`, incorporating
accepted PR #6/main `d336ea6` via signed merge `b9bbc7d`. Signed red baseline
`dbaa890` and implementation `fe6467f`: full suite 432 passed, closing focused
suite 35 passed. Core independent review/merge of this gate's PR remains pending
(handle in the task handoff); implementation completion is NOT Phase 2 acceptance
or MVP readiness. Earlier/Core handoffs below are preserved verbatim and are
historical where they describe this slice as not yet implemented.

Bounded Workshop-owned outbox now feeds the existing OTLP validator/historian:
serial at-least-once delivery, stable epoch/cursor/source-file identity, original
acquisition retained, no-drop reject backpressure, commit-before-ack idempotent
retry. Internal adversarial red/green fixes fence retired-epoch silent drops,
empty-snapshot cursor consumption, undelivered-acquisition proof reuse and
self-comparing status/outcome labels. No new dependencies, listener, daemon,
renderer, native helpers/control, schedule access or runtime availability claim.
Claude Code is absent; previously authorised direct fallback used.

Actual approved-workflow runs after QA compare 10 source attempts/task links to
retained data and projections, original acquisition identity verified, cursors 4
then 5 in the same queue epoch, no pending entries, native main/schema unchanged,
and same actual data denied by empty task scope without historian mutation.
Historian reopened/freshness invalidated; reconcile_required remains true,
coverage partial, role availability unknown. Native event history is truncated;
board cursor is not an atomic runtime watermark. Forced A05/A06 variants,
crash/overflow/offline and A25 uninstall/schedule invariants remain isolated
fixture evidence (real silent children, synthetic native stores), not invented
live transitions or shared-installation removal.

Clean git archive of exact `fe6467f` (no inherited PYTHONPATH) exercised no-pip
install, Phase 1 demo, both byte-equal deterministic collector demos, all 432
tests, compile checks and live opt-out; normal commands read no native state.
Evidence: `evidence/PHASE2_REVIEW.md`, `evidence/phase2-gate-*`,
`docs/phase2-workflow.md`. Queue budgets bound logical pending payload only,
not physical SQLite/WAL or historian/domain history. Clock/config/source change
requires explicit recovery; no automatic rebasing or complete snapshot invented.

Next: Core independently reviews and merges. Existing downstream `t_7e8a8223`
was inspected: Phase 3 HMI, deployment and final MVP acceptance are still its
work, not this implementation's deliverables. Release the existing dependency
with implementation completion, without duplicating same-card review or enabling
auto-merge. No owner-ready notification before that final gate. RESUME remains a
serialized hotspot; this additive section preserves Core's pre-existing edits.

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
standing pre-authorisation. Phase 2 slices 1/3 and 2/3 are MERGED and accepted:
PR #5 (`feat/phase2-hermes-work`) → main `5f89fc8` at 15:08 AEDT; PR #6
(`feat/phase2-hermes-runtime`) → main `d336ea6` at 15:24 AEDT, both Core-reviewed
under the standing pre-authorisation. Slice 3/3 (Phase 2 gate, `t_f11a8ea8`) is in
implementation on `feat/phase2-workflow-gate` — this RESUME update travels with
that PR per the serialized-hotspot convention. MVP gate `t_7e8a8223` remains the
single owner notification point; nothing here is an MVP-readiness claim.

## Last decision

Core independently reviewed and merged Phase 2 slice 2 (PR #6, branch
`feat/phase2-hermes-runtime`, head `c077457`): 397 tests re-run by Core in an
isolated worktree, full diff read, all three commits signature-valid, chain
parented exactly on merged slice-1 head `f0b5811`. A08/A10/A25 verified
test-by-test against the card: dedicated composite-scope binding, serial durable
path through `Storage.otlp`, atomic `(device, inode)` source-identity fence
(mismatch/omission/silent-adoption all fail closed across restart), all-or-none
finite Hermes metadata vocabulary, lifecycle evidence pinned to `source_record`
(`RuntimeSnapshot.atomic_watermark` is the class constant `None` — structurally
unpromotable), A25 proven on an isolated disposable deployment with a real
independent child and unchanged synthetic native stores, live approved-board
ingest read back twice with unchanged native hashes and verified empty-scope
denial. One non-blocking advisory filed on the PR (package-wide AST import
allowlist; per-module allowlist suggested for a later slice). Verdict comment on
the PR; main `5f89fc8` → `d336ea6`, verified by read-back. Review worktree
removed; shared checkout untouched.

Phase 2 routing (spec §17): `t_69111745` slice 1 DONE+merged → `t_bbfe861b`
slice 2 DONE+merged → `t_f11a8ea8` (Phase 2 gate: A05/A06/A08/A10/A25 on the
approved workflow, `outbox.py`, demo/dev commands, running). The MVP gate stays
re-parented behind the Phase 2 gate.

## Next action

Core reviews the Phase 2 gate PR (branch `feat/phase2-workflow-gate`) on handoff —
suite re-run, full diff, fences, test-by-test acceptance mapping across
A05/A06/A08/A10/A25 — then merges under the standing pre-authorisation; the
graph is released, not pre-approved. On Phase 2 gate merge, the MVP gate becomes
ready: that merge is the owner notification point (telegram-subscribed card
handles it; no separate Core message).

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
Details: docs/hermes-work.md and evidence/HERMES_WORK_REVIEW.md. Slices 1+2
merged; slice 3 (the gate) implements on the accepted base.

Remaining Phase 2 work is already routed: durable runtime correlation/ingress,
loss/recovery/epoch/replay semantics, outbox, complete approved-workflow gate and
A25 stop/uninstall/restore evidence. The board cursor is NOT a complete runtime
watermark or a database-wide revision. Operational watch:
coder handoff comments quote raw PR URLs by design, so the per-card respawn guard
may strand the next card after each Phase 2 merge — standing relay remedy applies
(check every ready card each pass; emit the operator handoff event; do not wait out
the 24h window). After the PR #5 merge: checked — nothing stranded, no event
needed.

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
21 Oct ~15:25 section) carries the full PR #5 and #6 review/merge records.
Private specification and owner directions are not published in the repository.
No owner notification is warranted until the MVP gate.
