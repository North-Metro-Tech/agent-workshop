# RESUME — Agent Workshop

## Objective

Build the read-only Workshop supervisory layer. Card t_dbf6fb11 (Phase 1 gate,
A10) is IMPLEMENTED on `feat/a10-phase1-gate`, PR #4:
https://github.com/North-Metro-Tech/agent-workshop/pull/4
Core independent review/merge is pending. Phase 1 is not accepted until that
merge; this is not an operational/MVP readiness notification.

## Last decision

Core independently reviewed and merged A08 PR #3: main/base `59696e9`, feature
head `a5baf48`, with 234 tests independently re-run and its original red baseline
reproduced. Its review is a PR comment/journal record because reviewer/author
share the publication identity. GenAI semconv revision `547934af` was resolved
in `open-telemetry/semantic-conventions-genai`, with Development-stability
caveat retained. This A10 branch builds on that merged base, not an open A08 PR.

A10 adds explicit trusted task instance/namespace permissions (empty denies),
runtime-instance uniqueness, synthetic-tested bounded read-only SQLite reads,
a deterministic synthetic snapshot demo and no-download source install/test/
demo/check commands. No native executor, route, enable switch or network
listener exists; controller positions cannot enable writes. Task authorization
is enforced consistently across CE, mapped OTLP and durable snapshot pages.

Signed red baseline `735bfbe`: 52 failed, 1 passed. Implementation `f7b5c82`:
294 full cases pass, including all prior A01–A04/A07–A09 and A10. Additional
materialisation red (1 failed, 5 passed) exposed fetchall exceeding aggregate
budget before rejection; reader now iterates incrementally. Exact-schema,
mode=ro/query_only, malformed/oversized input, unknown/view rejection and live
WAL/no-immutable cases are covered. Native content/schema is unchanged; WAL
SHM/coordination side effects are explicitly NOT claimed absent.

Actual clean git-archive run (no inherited PYTHONPATH): install, both demo
entrypoints (matching committed JSON), full 294 tests and Python 3.11/3.14
compile checks pass. Evidence and review focus: `evidence/PHASE1_REVIEW.md`,
`evidence/phase1-clean-checkout.txt`, per-scenario `phase1-A*.txt`, and raw
red/green captures. No dependency installed or updated. Claude Code unavailable;
authorised direct fallback used, not a provider/profile/credential workaround.

## Next action

Core independently reviews PR #4, re-runs gates and merges if sound. No auto-
merge enabled. Branch-protection lookup is denied HTTP 403; zero external
checks/statuses, if returned, are not a passing CI result. Exact-head publication
and checks are recorded in the Kanban handoff after the final signed doc push.

On merge, Phase 1 is accepted. Core routes Phase 2 (one approved real Hermes
workflow), then the renderer/remaining Release 1 work through the existing MVP
gate t_7e8a8223. That gate remains the owner's single readiness notification
point; its real-fleet/frontend/A05–A06/A23/A25 work is NOT completed by this card.
Do not treat released task dependencies as fulfilled downstream acceptance.

## Open question

None blocking A10. Phase 2 must supply approved actual schema mapping, source
identity and a genuine atomic source snapshot watermark; the SQLite primitive
is not a collector, native pagination/coverage protocol or runtime-liveness
proof. Exact task permission configuration is trusted local input. Old persisted
bindings reopen with empty permissions for future task links; retained facts
are preserved, not reauthorised silently.

Standing A08 contracts remain: serial service writer, dedicated configured
source/feed/role/runtime instance, comparable caller acquisition clocks, startup
freshness invalidation, complete supported runtime recovery only; replay
retention bounds checkpoints/journal, not domain/audit/dedup history. HTTP/SSE/
binary OTLP, live data and renderer are outside Phase 1. No type-check, coverage
percentage, benchmark, standards certification or external CI success claim.

## Coordination

Cards owned by coder; Core reviews and merges under the owner's standing
pre-authorisation. RESUME.md is the shared Core/coder hotspot: Core's post-A08
handoff was preserved during implementation and serially merged here once.
Private specification and owner directions are not published in the repository.
