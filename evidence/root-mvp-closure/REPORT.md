# Root MVP gate recheck — OPEN on new development-audit advisory

Task: `t_7e8a8223`, run 42, 25 October 2026 AEDT.
Exact reviewed/deployed product: `5f7df84da20206a89d87a8ed692dff537edfefc4`.
Local-only QA/documentation branch: `docs/release1-mvp-closure`.

## Result and required decision

**Do not close the root or send “Workshop MVP is ready” yet.** Owner actual-use
PASS is accepted from Core's completed final sweep `t_a87670b9`; it is NOT the
remaining blocker. Fresh dependency metadata introduces one development-only
high advisory that was absent from the earlier recorded audit. Production-only
audit is clean. Core must explicitly disposition this scoped risk or route the
smallest compliant remediation and independent checks. This root does not waive
an audit, perform a dependency repair, install an exploit, or override quarantine.

`npm-audit.txt` and `npm-audit.json.txt` preserve actual exit 1:
- Package: exact devDependency `happy-dom@21.0.1`.
- Advisory: GHSA-834v-8h66-3h79 / CVE-2026-115895.
- Affected metadata range: >=17.0.0 <=21.0.3; patched: 21.0.4.
- Advisory requires enabled JavaScript evaluation plus attacker-controlled module
  or HTML input. Our inspected configuration uses Happy DOM for Vitest, synthetic
  test data only; it is not a production application import. This bounds the
  exposure; it does not make the full development audit pass.
- Fresh `sfw npm audit --omit=dev --json` exits 0, zero production advisories.
- Registry `happy-dom-publication-times.txt`: 21.0.4 published
  **2026-10-20T18:05:53.295Z**. Seven-day eligibility is
  **2026-10-27T18:05:53.295Z / 28 October 05:05:53.295 AEDT**.
- The fix was 4.535 days old at the recorded query; no age exception exists here.
  No `npm audit fix --force`, dependency/lock update, downgrade, suppression,
  threshold change or new external package was used.

Recommendations for Core: decide whether the trusted, synthetic-only development
use can carry a time-bounded, explicitly recorded release risk until the patch's
eligibility, or commission a narrow mitigation/remedy with its proper gates.
Only PO may grant a quarantine exception. Owner readiness remains the root's one
notification, not a new notification from a remediation lane.

## Real checks performed in a clean clone at the installed product

The checkout was created with `git clone --no-hardlinks` from the installed
checkout, initially clean at the exact product head above. No installed files,
service settings, native stores, profile configuration or dependencies changed.
Claude Code is still absent; previously authorised direct verification tooling
fallback was used, not self-approval or independent implementation review.

| Check | Actual result | Raw evidence |
|---|---|---|
| Full backend | 568 passed, zero failures/errors/skips | backend-tests.txt, backend-junit.xml |
| Exact frontend typecheck/test/build | All exit 0; 57 tests | frontend-typecheck.txt, frontend-tests.txt, frontend-build.txt |
| Backend-generated schema | Check exits 0 | schema-check.txt |
| Real provisioned Chromium/TCP synthetic service | Four passed; zero skipped/flaky/unexpected | browser.txt, browser.json |
| Existing lock quarantine | Python and all npm lock resolutions pass | python-quarantine.*, npm-quarantine.* |
| Socket-wrapped exact existing lock installs | Both exit 0 | python-socket-install.txt, npm-socket-install.txt |
| Full dev audit | FAIL: one high Happy DOM advisory | npm-audit.txt, npm-audit.json.txt |
| Production-only audit | PASS: zero advisories | npm-production-audit.json.txt |
| Clean install, installed demo, both repeatable demos, compile | All exit 0; both repeat outputs byte-equal | clean-install.txt, *demo*.txt, compile.txt |
| Actual loopback and authorised HTTPS | Both 200; no new proxy or listener configured | loopback-http.txt, tailnet-http.txt, serve-status.txt |
| Two approved Phase 2 actual acquisitions | 42/42 execution/task comparisons agree each time | one-shot-workflow-1.json, one-shot-workflow-2.json |
| Actual installed HTTPS Chromium | PASS; actual run42 -> this root, all42 native task/lifecycle links agree, login/session/SSE/canvas/detail/local-only controls | live-browser.txt, browser-report.json |
| Exact durable schema2 snapshot readback | Both responses equal reconstructed revisions92504/92505 | historian-readback.txt/json, browser-snapshot-*.json |
| Native fence over recorded browser window | Main/schema equal; WAL/SHM excluded | historian-readback.json |
| Installed service | active/running; Restart=no, NRestarts=0, boot disabled; original 24Oct22:02 start preserved | live-service.txt |

Fresh transport quality is NOT proof of execution freshness. After the authorised
same-boot restart, the designed reconciliation latch keeps source acquisition and
lifecycle quality unknown until supported complete recovery. Current canonical
run42 contains `acquired_at=unknown`, `acquisition_age=unknown` and
`lifecycle_quality=unknown`, correctly preserved in the DOM. The first adapted QA
script incorrectly demanded a numeric age; its failure and captured response are
preserved under `live-attempt1/`. The corrected evidence checks unknown EXACTLY
against the canonical snapshot, requires numeric nonnegative ages only when the
canonical acquisition is known, and retains every lifecycle/task/session/authority
assertion. No product code, source freshness rule or acceptance boundary changed.
This conservative restart limitation is already documented in RESUME/ingress
contracts and must not be described as fresh execution progress or availability.

## Existing independent acceptance, not relabelled as fresh root scenarios

- Final sweep `t_a87670b9`: Core completion and explicit owner actual-use PASS,
  25October desktop via authorised tailnet path. New product presentation/control
  direction is Release2 planning, not an invented Release1 nonconformance.
- Twelve §16 transcripts: signed evidence `df2ef871a6f45c1c82d65bb055ac500403fce80f`,
  under `evidence/A01.txt` through `A10.txt`, `A23.txt`, `A25.txt`, at product
  d56e3ccf. These were freshly executed in that sweep; root verifies their Git
  blobs and pinning tests, NOT renaming them as fresh5f7df84 scenario runs.
- Earlier independent scenario review: `t_4002229b`; Phase3 exact audit:
  `t_86139b05`, findingsF1/F2/F3 closed, §19.5/MIT/extraction boundary accepted.
- Tailnet exact-origin review/merge/state-preserving delivery: `t_65bd6a42`;
  merge5f7df84 has independently approved tree equality to candidate29152282.
- Bounded schema2 installation: `t_2ec73616`, evidence7994558. Its finite
  sustainment window is not a30-day capacity proof.

This run changes only local evidence and one additive RESUME entry. All prior
RESUME text and installed product remain preserved. No push/PR/merge, deployment,
service restart, schedule access, native acknowledgement/command, owner message,
full-fleet health, manual assistive-technology speech, qualitative image review or
30-day validation is claimed. Owner first use is recorded, but daily-use records
and write-up remain a separate post-root activity. Native actual coverage stays
partial and availability unknown. Requested systemd restrictions are not proof of
an effective kernel read-only mount; the observed native path is under rw root.
