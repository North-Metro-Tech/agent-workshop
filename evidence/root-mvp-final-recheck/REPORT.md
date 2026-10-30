# Root MVP final recheck — NOT COMPLETE: new live agreement decision

25 October 2026, ~18:27–18:30 AEDT. This report supersedes the **audit blocker** in the historical `../root-mvp-closure/REPORT.md`, not its immutable evidence. **MVP is not declared ready. No owner-ready notification.**

## Accepted prerequisites, unchanged

Core completed `t_817d72ca`: accepted time-bounded **dev-only** Happy DOM21.0.1 HIGH GHSA-834v-8h66-3h79 (CVE-2026-115895), under trusted synthetic-input boundary. This is NOT a clean dev audit or age exception. Production audit is clean. Exact21.0.4 patch `t_89910f17` remains quarantined until 28Oct05:05:53.295AEDT; independent Core review/merge is `t_d2afc283`. Owner actual-use PASS on `t_a87670b9` remains accepted, not reopened. The30-day use record is outside the root gate.

## Fresh real execution

- 568 backend tests, zero skips (`backend-tests.txt`, `backend-junit.xml`).
- 57 frontend tests; typecheck/build PASS (`frontend-*.txt`).
- Four actual synthetic-source TCP/Chromium tests, expected4/skipped0/unexpected0/flaky0 (`browser.json`, `browser.txt`, screenshot). Original generated tracked scene restored; product/evidence outside this new directory unchanged except additive RESUME.
- Schema check, compile check, repeatable synthetic demo/collector-demo PASS.
- Actual full dev audit exits1, exactly one HIGH Happy DOM, unchanged accepted risk (`npm-audit.json`); production-only audit exits0, zero vulnerabilities (`npm-production-audit.json`). No suppression/new packages.
- Pure readback of signed fb56ff6 checkpoint passed before this additive update (`preserved-checkpoint-readback.txt`). That checkpoint remains historical; its root-HEAD assertion is not expected to pass after this new documentation commit.

## New failure — not a failing unit test or a fresh audit objection

`run-final.py` is the exact final QA driver. It stopped at the first bounded `scripts/observe_workflow.py --approved-local` call: exit1, `ValueError: Source/projection disagreement for attempt 42`. `one-shot-workflow-1.json` intentionally preserves its raw **non-JSON traceback**, not a successful acquisition. Do not parse it as JSON or report final driver completion. The second planned acquisition, full old live-agreement browser, and scenario-copy section were **not executed**. No outputs are fabricated.

The existing isolated `.workshop-state` had observed attempt42 running in acquisitions1/2. Fresh acquisition3 now has blocked/blocked -> mapped unknown, and the delivered raw OTLP record retains that change; canonical lifecycle remains earlier active. The private QA historian was NOT reset/deleted to hide the transition.

`diagnose-agreement.py` uses only bounded approved native observation and `mode=ro`+`query_only` historian reads. `agreement-diagnostic.json` shows the same behavior in **both isolated QA and the installed historian**:

| Attempt | Current native mapping | Canonical retained mapping | Canonical lifecycle quality |
|---|---|---|---|
|42, previous root run|unknown (blocked/blocked)|active|unknown|
|43, Core advisory decision|succeeded|succeeded|unknown|
|44, scheduled patch card|unknown (unsupported scheduled status)|active|unknown|
|45, current root run|active|active|unknown|

`live-diagnostic.mjs` independently logs into the **actual installed HTTPS origin**, captures these canonical values and verifies current run45->root keyboard detail, SSE advancement and fixed-off native control. Result is explicitly **MISMATCH_REPRODUCED_NOT_MVP_PASS**, not all45 agreement. No assertion was relaxed to transform disagreement into acceptance.

### Mechanism to classify, not a coder-authorised product change

`backend/workshop/ingest.py:318-319` invalidates acquisition under reconciliation latch. Lines395–410 then reject nonterminal replacements without comparable acquisition/native revision. HermesRuntime's payload has no native execution revision. New raw records are retained, terminal facts may still advance, but active->unknown cannot replace the prior canonical fact under that contract. This looks consistent with conservative historical-fact preservation, yet the accepted workflow verifier explicitly demands current source lifecycle equality and now fails. Neither declaring that harmless nor changing ordering/lifecycle/verification semantics is justified solely by the green test suite. Core must classify intent and route the narrow repair/contract correction with regression evidence.

## Installed evidence still good, bounded claims only

`historian-readback.json` reconstructs the captured schema2 revisions **93700/93701** from their actual anchor/delta chains: all72 browser items equal their exact durable revision, native identity and original record identities match. This proves browser/historian consistency, **not** source/canonical agreement. Native main/schema unchanged during the measured interval; excludes WAL/SHM coordination and concurrent-writer attribution.

`live-service.txt`: active/running, Restart=no, NRestarts0, boot disabled, same24Oct22:02 start. No installed source, lock, runtime, native store, schedule, observer state reset or service restart changed by this work. Test-only local sessions and approved read-only source interactions only. Runtime coverage partial, role availability/lifecycle quality unknown; no full fleet/atomic watermark/manual AT/30-day capacity claim.

## Routing and preservation

New Core/default prerequisite **t_38604cb5** classifies this final live-contract disagreement and owns any follow-up routing; linked as a parent of root **t_7e8a8223**, NOT vice versa. It is independent of already-accepted owner review and advisory risk. The root stays incomplete and emits no readiness notification. Core must encode any implementation/review prerequisite in the graph before releasing it. `default` is an installed profile (confirmed via profile list).

This is an evidence/documentation-only signed checkpoint on `docs/release1-mvp-closure`, over fb56ff6, with additive RESUME preserving all previous text. Original failed proof and all prior closure evidence untouched. New manifest/verifier check exact raw test counts, preserved failure, two lifecycle mismatches, captured durable equality, service guards and103 non-evidence product files byte-equal approved installed5f7df84d. `verify-recheck.py` checks the new evidence without reopening rolling old revisions. Durable evidence archive/bundle location and signed commit are recorded in the Core/root handoff. No push, PR, merge, deployment, independent self-approval or MVP-ready claim.
