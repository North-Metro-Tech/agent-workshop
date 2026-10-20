# RESUME — Agent Workshop

## Objective

Build the read-only Workshop supervisory layer. Current card t_9466d0f8 is the
Phase 1 A07/A09 function-level CloudEvents + OTLP observation-mapping slice on
the merged A01–A04 reducer (PR #1, base 9f8e876). It is not full Phase 1,
a renderer, collector, live integration or HTTP service.

## Last decision

Authorised repository is North-Metro-Tech/agent-workshop, public Apache-2.0.
The old provisioning/transfer blocker is resolved: PR #1 was independently
reviewed and merged. This slice is on feat/a07-a09-wire-ingest; no main push.

Implemented bounded transactional CE/OTLP JSON ingestion, stable identity and
changed-body protection, native-revision/acquisition ordering, retained terminal
and conflict invariants, privacy allowlists and trusted acquisition context.
Unknown acquisition is None, never receipt-derived freshness. Collector restart
invalidates source live evidence and forces reconciliation; no ordinary event
can clear that latch. Snapshot/historian recovery belongs to the next slice.

Signed executable red baseline 7436aae: 83 failures before implementation.
Adversarial assertion-red captures: 17 failures, 4 provenance failures and 2
scope-metadata failures, all fixed. Final suite: 182 passed, including the
existing 66. Python 3.11 and 3.14 compilation and whitespace checks passed.
Exact captured outputs and
limitations: evidence/INGEST_REVIEW.md and adjacent a07-a09-*.txt files.

No dependencies were installed; Claude Code remains unavailable, so the Lead
used the documented direct-implementation exception. No provider/model/profile,
credential, native database or runtime configuration was changed.

## Next action

Core independently reviews the feature PR against main; the exact publication
URL/head and evidence are recorded on this card's lifecycle handoff after
read-back verification. Core reviews and merges (pre-authorised by the owner);
implementer must not
self-approve, enable auto-merge or mark the engineering change finally accepted.
After review, continue only with the separately authorised Phase 1 cards.
The task graph now includes the downstream MVP QA/release gate, so completion
of this implementation phase releases existing children; it is not independent
approval of PR #2. Downstream work must use the verified parent PR head and
coordinate Core's merge, not assume unmerged main contains this slice.

## Open question

The supplied GenAI semconv revision 547934afa90a34298441caf80c43b27255c3a292
returned upstream HTTP 422. Kept verbatim in docs/standards.lock; Core should
confirm its source. No substituted pin or upstream-conformance claim is made.
This no-transport slice maps standard OTLP JSON; binary HTTP/protobuf binding
and SDK compatibility are explicitly not implemented or claimed here.

## Coordination

Board card t_9466d0f8, coder. RESUME.md remains a shared Core/coder collision
hotspot: serialize handoff edits. Private specification and owner-direction
source documents are referenced only on the task card, not published here.
