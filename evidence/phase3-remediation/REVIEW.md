# Phase 3 F1–F3 implementation handoff (not MVP acceptance)

Task: t_1503dfef. Branch: `fix/phase3-service-history-annunciation`.
Base: `ce52227c983598dcbb951f3c1d2ff55fe354ccdf` on `feat/phase3-mvp`.
The exact signed delivery SHA and PR URL are recorded in the task handoff/PR;
this report travels in that commit and does not contain a self-referential SHA.
No auto-merge, self-approval, deployment or owner-readiness claim.

## Requested and delivered

F1: actual Uvicorn HTTP/SSE service instead of mock-only client contracts.
`backend/workshop/service.py` owns Storage on one asyncio loop, rejects a second
service writer before opening the historian, periodically acquires only the
explicit approved-local mode, and exposes bounded snapshots/history and FULL
SSE snapshots. Foreign/future/expired/malformed cursors request a reset followed
by a full snapshot. Periodic same-revision snapshots update acquisition ages;
older same-revision generation times cannot replace newer facts in the client.
Cookie login is provisioned locally; exact Host/Origin, no trusted proxy headers,
HttpOnly/SameSite Strict cookies, session expiration/rotation, rate/capacity
bounds and operator+CSRF authority fence Workshop-local acknowledgement.
There are no native control routes or enable-write switch.

`web_contracts.py` is authoritative Pydantic; `scripts/generate_schema.py`
produces `docs/web-schema.json` and replaces the old handwritten `generated.ts`.
Unknown generator schema constructs fail closed; `--check` verifies exact bytes.
`dev.py serve/schema` and README provide first-user setup, private mode-600
secret provisioning, exact loopback URL and explicit source-mode instructions.

F2: `Storage.retained_diagnostics()` reads one detached historian transaction,
returning at most 100 retained observations/local alarm audit entries with
stable identity and provenance. Timeline explicitly labels historical semantics,
uncertain cross-source ordering and unavailable per-observation acquisition times.
Its excerpt cursor is displayed separately from the live snapshot. Old async
history responses cannot repopulate a changed historian identity. New browser
process and service restart tests compare retained entries and verify revoked
sessions and invalidated current freshness. No raw transcripts, native file
browser or arbitrary database query is exposed.

F3: one polite atomic live region batches material alarm transitions, suppresses
initial inventory and identical repeated states, limits announcement details and
retains first-out uncertainty. Distinct same-label occurrences are observable.
Announcements do not move focus or override reduced motion. Regressions include
same-text transitions, removal/identity reset, disconnected states and actual
HTTP acknowledgement with focus held on a stable control.

## Actual validation and raw evidence

All final commands exited zero. Paths below are relative to this directory.

- `backend-final.txt`: 466 passed (27.37s), including all prior 432 cases.
  Command: `PYTHONPATH=.venv/lib/python3.11/site-packages:backend:collectors /home/aaron/hermes-agent/.venv/bin/python -m pytest -q`.
- `service-final.txt`: 34 passed; verbose named tests in
  `backend/tests/test_service.py`, using real Uvicorn/TCP plus the documented
  secret-provisioning CLI (not ASGI mocks).
  Same interpreter/path prefix, `-m pytest backend/tests/test_service.py -v`.
  Covers bad Host/Origin, absent/expired/rotated sessions, open-stream expiry,
  missing/invalid/Unicode CSRF, viewer/body authority spoofing, malformed mutation
  revisions, malformed/foreign/future/expired SSE cursors, durable ack/restart,
  historian bounds/detachment, source-mode/single-writer fences, Unicode secrets
  and bounded observation serialization.
- `frontend-final.txt`: 57 passed in five test files.
  `npm --prefix frontend run test -- --run`.
- `frontend-typecheck.txt`, `frontend-build.txt`: exact `typecheck` and `build`
  scripts both passed. Generated schema check: `schema-check.txt`.
- `browser-final.txt`: FOUR passed, ZERO skipped.
  `WORKSHOP_E2E_CHROMIUM=/home/aaron/.local/bin/chromium npm --prefix frontend run test:e2e`.
  This provisions an isolated synthetic TCP service/random secret/historian and
  tests canvas pixels plus DOM facts/keyboard/reduced motion, network reconnect,
  new browser process/service restart, retained diagnostics, session revocation,
  reauthentication without manual reload and actual local ack/live-region focus.
  No browser download, response interception, native acquisition or service skip.
- `startup-final.txt`: documented `init-secret` created a mode-600 private file;
  actual `dev.py serve --synthetic` returned index HTTP 200 and unauthenticated
  session HTTP 401. `startup-first-run.txt` retains a real discovered CLI failure:
  `Path.open` does not accept `opener`. Fixed to built-in `open`, and a regression
  now verifies private permissions, no printed secret and no overwrite on retry.
- `python-compile.txt` (empty successful stdout), `demo.json`,
  `collector-demo.json`: `.venv/bin/python scripts/dev.py check/demo/collector-demo`
  all passed. Demos remain synthetic, no live source reads.
- `python-quarantine-audit-final.txt` and matching JSON: all FOURTEEN Python
  resolutions match authoritative PyPI hashes, publication ages >=7 days, no
  yanked files or known PyPI/OSV advisories. `requirements.lock` is fully pinned
  and hashed; Linux x86_64/Python 3.11 is the verified installation target.
- `python-socket-install-final.txt`: Socket-wrapped hash-required binary-only
  exact reinstall succeeded. `python-dependency-check.txt`: dependency check
  passed. `python-resolution.txt` and install/debug transcripts preserve earlier
  resolver/Socket evidence (including failures, not a claimed all-green history).
- `npm-quarantine-final.txt` plus refreshed `../phase3-npm-quarantine.json`:
  all 99 lock resolutions pass registry age/integrity/tarball checks.
  `npm-socket-install-final.txt`: Socket-wrapped ci passed.
  `npm-audit-final.txt`: full audit, zero vulnerabilities (includes dev tooling).
- `browser-first-run.txt`, `browser-second-run.txt`, `backend-wip.txt` and other
  first/WIP outputs are historical attempts, not final passing evidence. The
  browser first failed an exact age comparison against advancing monotonic time;
  revised assertions keep fact equality and allow only bounded age advancement.
  Later restart reauthentication and focus/live-region issues were corrected and
  regression-tested. Raw failures are retained, not rewritten as successes.

Approved dependency scope: the recorded frontend ruling plus minimal Uvicorn
(no standard extras) and necessary FastAPI/Pydantic runtime transitives. No new
unapproved package, quarantine exception or harness/provider change was used.
Claude Code was absent; the task records the authorized direct fallback. Internal
bounded QA and Lead reruns are production QA, NOT independent approval.

## Limitations and reviewer attention

- Local HTTP loopback only, one process/one writer, trusted local filesystem/OS.
  No public/proxy/TLS/multiworker claim. Cookies are intentionally not Secure on
  loopback HTTP. A hostile local user or same-origin XSS is outside this boundary.
- Lifetime flock coordinates this service, not arbitrary external Storage writers.
  Source-mode/boot-clock sidecar mismatch fails closed; no automatic rebase,
  migration, TOCTOU/hardlink defense or boot-recovery implementation is claimed.
- Bounded diagnostic output is NOT a physical whole-historian/domain retention or
  throughput guarantee: Storage still loads retained domain state. Snapshot
  output is capped; oversized/unrepresentable domain projections fail instead of
  inventing completeness. Timeline ordering is not global causal/time order.
- Only current approved Phase 2 scope is available under explicit approved-local
  startup. This implementation run used synthetic service fixtures ONLY; actual
  fleet installation/workflow proof belongs to downstream t_2ec73616.
- Manual assistive-technology speech is unverified. The screenshot
  `browser-scene.png` is a real Playwright capture, but the image-analysis provider
  returned an invalid-API-key error, so no manual/model visual verdict is claimed.
  Automated pixel/DOM, focus and reduced-motion checks passed.
- Original Pixel Agents extraction/visual code and licenses are unchanged by this
  remediation. Independent exact-head boundary/controls re-audit is still required.
- No full twelve-scenario rerun, clean-checkout acceptance, external CI success,
  Core approval, merge, deployment or MVP-readiness is claimed on this card.

## Downstream handoff / ordering

Existing child cards inspected: t_86139b05 re-audit, t_4002229b scenario rerun,
t_f429ab51 clean-checkout QA, t_2ec73616 installation, t_a87670b9 final sweep,
t_7e8a8223 root. Complete this implementation phase to release the precreated
re-audit, not same-card review (which would strand it).

Core independently reviews/merges this PR to `feat/phase3-mvp`; do not auto-merge.
The current graph makes t_4002229b depend on t_86139b05, although the re-audit
body's historical narrative asks for scenario reconciliation first. Re-audit must
not wait for its own gated child: use the real A08/A23 service/browser evidence
and rerun at exact head; report the remaining twelve-scenario reconciliation as
downstream, coordinating Core if any gate ordering needs changing. No edge was
changed by this implementation. t_f429ab51 remains operator-blocked until Core's
specified unblock; all deployment/final gates remain intact.

RESUME.md received one serialized additive section; prior Core/coder text is
preserved. It remains a shared hotspot. No separate owner notification.
