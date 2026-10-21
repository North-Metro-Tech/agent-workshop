# RESUME — Agent Workshop

## Objective

Build the read-only Workshop supervisory layer. Card t_f6e9e637 delivers the
Phase 1 A08 durable historian and atomic snapshot/replay recovery slice on
merged A01–A04 + A07/A09 (PR #2, main ddbf893). Not full Phase 1, live operation,
a renderer, native collector or HTTP service.

## Last decision

Feature branch feat/a08-durable-recovery targets main. PR #2 was independently
reviewed and merged; its old pending-review handoff is superseded.

Workshop-owned SQLite WAL + explicit migration now persists domain state,
alarms/occurrences/audit, source dedup/order/epoch indexes and revision checkpoints.
Snapshots use a declared page manifest, scope, epoch and trusted atomic source
watermark; journaled newer effective keys preserve lifecycle fields while all
history/conflicts survive merge. Partial/weak evidence cannot establish covered
runtime inventory, erase unseen records or restore restart freshness. Complete
absence never fabricates a terminal state. Startup invalidates live clocks and
coverage without losing facts. Atomic projection/service cursors support bounded
browser-style replay and explicit snapshot reacquisition on expiry. Local alarm
acknowledgement is durable when using the historian-backed facade; native writes
remain disabled.

Signed test-first red baseline efdc872: 1 failed + 33 stub setup errors.
Adversarial assertion-red captures: 9 failures plus 1 cross-role correlation
failure, fixed and preserved. Full suite: 234 passed; storage subset 52 passed.
Python 3.11.15 + 3.14.7 compilation and whitespace checks passed. See
`evidence/STORAGE_REVIEW.md`, `evidence/a08-*.txt` and `docs/storage.md` for actual
output, acceptance mapping, contracts, risks and limitations.

No dependency installs, native/live databases, provider/model/profile changes
or runtime configuration changes. Claude Code absent; Lead used the authorised
direct-implementation fallback and reviewed real tests/diffs.

Core's standards correction is applied: unchanged GenAI revision
547934afa90a34298441caf80c43b27255c3a292 is resolved in
open-telemetry/semantic-conventions-genai (Core verified HTTP 200 on 21 October;
commit 18 October 2026). Earlier 422 queried the wrong repository. Development
stability remains; no upstream-conformance certification or dependency adoption.

## Next action

Core independently reviews and merges the feature PR under the owner's standing
authorisation. Published PR URL/exact head/signatures/check evidence are recorded
on card t_f6e9e637 after external read-back. Implementer does not self-approve,
enable auto-merge or merge. The task graph already includes A10 and MVP QA/release
children: implementation completion releases those dependencies, not final
engineering acceptance. Downstream work must coordinate Core's merge or use the
verified parent PR head, not assume unmerged main has the historian.

## Open question

No blocking design question within A08. Review the documented trust contract:
adapter-supplied stable source sequence/atomic source watermark and comparable
acquisition clocks; one serial service writer with dedicated source/feed/role.
Local mutations overlapping snapshot collection conservatively require a fresh
snapshot. Replay retention bounds checkpoints/journal, not all domain history,
audit or dedup indexes; full-state checkpoint writes are correctness-first,
not a throughput or total-disk-bound claim. Native binding/A10, HTTP/SSE/binary
OTLP, outbox/archival policy, renderer and runnable demo remain later work.

## Coordination

Card t_f6e9e637, coder. RESUME.md is the shared Core/coder hotspot: serialized
handoff edit. Private specification/owner directions are not published here.
