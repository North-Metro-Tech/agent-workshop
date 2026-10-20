# RESUME — Agent Workshop

## Objective

Build the read-only Workshop supervisory layer. Card t_941ea707 is strictly the
Phase 1 A01–A04 synthetic truth-model reducer slice, not a renderer, live
integration, fleet change or full Phase 1 completion.

## Last decision

Core corrected the authorised destination to the North-Metro-Tech organisation
using the existing operations-journal precedent. The intended public,
Apache-2.0 repository is North-Metro-Tech/agent-workshop; origin already points
there. This supersedes the older vitruvius-nmt destination in the original card.
Remote provisioning is an owner action, already recorded by Core; this worker
has not changed credentials. Current gh and git lookups cannot find/access it.

The feature branch feat/a01-a04-truth-reducer now implements concurrent identity
and explicit correlation, coverage and reconciliation-gated availability,
per-feed/per-field freshness, local alarm occurrence/incident semantics and a
read facade with the native-write interlock fixed off.

Real executable red baseline: 42 failures before implementation. Adversarial QA
captured and fixed five failing false-authority/availability regressions plus
one cross-role identity-conflict regression. Final full suite: 66 passed. Compilation and whitespace
gates passed. Exact evidence and limitations are in evidence/REVIEW.md and its
adjacent captured output files. No live source or native database was targeted.

Claude Code was not installed in the execution environment, so the Lead used
the documented direct-implementation exception. No dependencies were installed,
and no model/provider/profile or credential configuration was changed. Delivery
roster remains editorial + coder, with the existing model-route lock unchanged.

## Next action

Owner provisions or grants existing-identity access to
North-Metro-Tech/agent-workshop. Then push only feat/a01-a04-truth-reducer,
open the PR against main, verify its remote head, and call kanban_request_review
with PR URL, changed files and recorded test evidence. Do not merge or mark
this card done before review. No further implementation scope is authorised.

## Open question

Remote provisioning/access is the remaining delivery blocker, not a local
fixture blocker. No PR URL or remote CI evidence exists yet. Core's prior note
about isolated-profile versus host-mode gh identity remains unresolved; no
credential work is authorised on this card.

## Coordination

Board: agent-workshop, card t_941ea707, assignee coder. RESUME.md was a bootstrap
collision hotspot: guarded writes preserved Core's namespace correction before
this handoff update. Use the task card for private specification/owner-direction
references rather than publishing those source documents into this repository.
