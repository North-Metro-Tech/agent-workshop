# Exact-set tailnet origin — implementation and review handoff

Task: t_989a6842. Owner decision: 24 October 2026.
Base: `feat/phase3-mvp` at `d56e3ccf6f332fd4b578fa47cd2e2a7f24a726d4`.

## Result and scope

Implementation is ready for independent Core review, NOT deployed or MVP-ready.
Claude Code is absent in this environment; the Lead used the established direct
repository-tooling fallback. Internal QA is not independent approval.

- Add optional `Settings.extra_origin`, populated only from
  `WORKSHOP_EXTRA_ORIGIN` by the existing serve entrypoint.
- Validate one plain ASCII HTTPS `.ts.net` origin; reject HTTP/public/bare-IP,
  userinfo, path/query/fragment, list/whitespace/control-character, malformed DNS
  and malformed/zero/out-of-range port inputs at startup.
- Boundary builds immutable exact byte-membership sets from primary plus optional
  extra. Host and Origin independently belong to their approved sets. No request
  suffix/regex/wildcard matching, forwarded-header trust or CORS changes.
- Preserve the original duplicate authority/origin/cookie, Sec-Fetch-Site,
  mutation Origin, query, body-size, session/CSRF/permission and response-security
  checks. Bind stays 127.0.0.1; `proxy_headers=False`; one worker.
- Add the exact unit drop-in under `docs/systemd/`; it is staged configuration,
  not an already-installed change. Add tracked OPERATOR.md preserving the prior
  installed text and appending the owner decision; README points to its narrowly
  authorised exception. No RESUME, Pixel Agents, native control or data changes.

Approved extra: `https://frankenfarm.taile4f46c.ts.net:10000`.
The hostname without `:10000`, siblings/subdomains and all other ports reject.
The `.ts.net` suffix check is configuration validation ONLY, not caller identity
or device ACL enforcement. Only Aaron's named owner devices are authorised;
Tailscale enrolment/ACL administration and actual-use judgement remain separate.
Funnel/public exposure remain forbidden. Existing cookie Secure=False is
unchanged for loopback compatibility and explicitly documented; tailnet transport
must be HTTPS. No new authentication or hostile-local-user protection claim.

## Executed validation

Raw results are in this directory; `verify_candidate.py` reconciles JUnit and
Playwright counts, compares protected product files with Git blobs and checks
the drop-in and added-line security scan.

- Fresh exact-base isolated clone: **494 passed**, zero failed/error/skipped.
- Candidate full backend suite: **568 passed**, zero failed/error/skipped;
  **74 additive tests** in `backend/tests/test_tailnet_boundary.py`.
- Every original backend test, every collector and tracked frontend file, and
  dependency manifests/locks byte-equal the approved base: 60 protected files.
- Frontend: typecheck PASS, **57 tests passed**, production build PASS.
- Pydantic schema generation `--check`: PASS, no schema/product drift.
- Actual isolated synthetic TCP/Chromium suite: **4 passed**, zero skipped,
  unexpected or flaky; includes session/SSE/restart/retained-history/local ack.
- New real-TCP tests: tailnet static GET/login/session/CSRF/ack positive; original
  primary login with extra enabled; exact host/port/scheme/origin negatives;
  missing mutation Origin; X-Forwarded-* and Forwarded cannot substitute and do
  not override legitimate headers; duplicates/fetch-site/query/preflight remain
  rejected; optional extra absent stays loopback-only; config/startup guards.
- Added-line static security patterns: no literal credential, shell injection,
  eval/exec, pickle or interpolated SQL hit. Actual installed login secret absent
  from every evidence artifact. No secret/cookie recorded in live readback.
- `git diff --check`: PASS after removing one documentation EOF blank line.

No package was installed or updated. Python testing reused existing approved
Python 3.11.15/pytest and installed locked runtime packages through PYTHONPATH;
frontend used a copy of installed node_modules. This is a no-new-dependency
change, not a fresh supply-chain audit/install claim.

First additive-test attempt failed on two TEST HARNESS assumptions, retained as
`attempt1-new-tests.txt/xml`: h11 can return 400/reset on duplicate Host before
ASGI (the test now asserts rejection status without reading its error body), and
the mocked CLI plumbing test needed its own built-index fixture. Product logic
was unchanged by those fixes. All original tests remain unchanged. The browser
suite overwrote its historical screenshot; the fresh image was copied here and
only that generated historical image restored. No qualitative visual or manual
screen-reader review is claimed.

## Actual live read-back BEFORE deployment

`live-before.json` and executable `verify_delivery.py` record actual transport:
loopback 200, tailnet HTTPS 403, foreign Host 403, missing/wrong port 403 and wrong
scheme Origin 403. Original live historian inode/identity/cursor and binding
checksum are captured; authenticated snapshot has native writes fixed off.
Service remains active/running, Restart=no, boot autostart disabled. Serve's
:10000 route targets the existing loopback; no AllowFunnel enabled. Shared Serve
configuration is unchanged. No live checkout/unit/state mutation or restart was
performed in this implementation phase.

## Required independent Core review and reviewed delivery

Core must independently inspect exact PR head and rerun meaningful gates, then
merge to `feat/phase3-mvp` under standing authorisation. Do NOT deploy unreviewed
code, self-approve, arm auto-merge, or claim missing CI passed. No external CI is
claimed by this report. Reviewer should focus on exact netloc/port membership,
config parsing ambiguity, unchanged Origin/CSRF checks, and the bounded operational
exception to the old documentation prohibition.

After approval/merge, Core's delivery gate owns the following authorised work:

1. Recheck live service and clean installed checkout at
   `/home/aaron/.local/share/agent-workshop/release1/checkout-schema2`.
   Verify the merged tree contains this exact candidate. Preserve all existing
   schema2 historian/outbox/secret/binding files and original schema1 diagnostics.
2. Before updating, capture a fresh baseline (save outside the checkout):
   `python3 evidence/tailnet-origin/verify_delivery.py --expect-extra disabled`.
   Check schema2 state is healthy; no automatic retry/recovery/replacement.
3. Fetch approved `feat/phase3-mvp` into the existing installed checkout and
   fast-forward only. No reinstall, dependency resolution or data migration.
   Frontend/requirements remain byte-identical, existing dist and .venv stay put.
4. Install ONLY `docs/systemd/agent-workshop-release1.service.d/tailnet-origin.conf`
   into the matching directory under `~/.config/systemd/user/`. Preserve all
   original main-unit settings, especially Restart=no/disabled autostart.
   Copy candidate OPERATOR.md to the existing outer release1/OPERATOR.md.
5. `systemctl --user daemon-reload`; deliberate
   `systemctl --user restart agent-workshop-release1.service` once, same boot.
   If it fails, stop/escalate; never remove binding/lock/state to force success.
6. From the candidate evidence directory's repo, run:
   `python3 evidence/tailnet-origin/verify_delivery.py --expect-extra enabled --before <fresh-baseline.json>`.
   This asserts actual loopback200/HTTPS-tailnet200/foreign403, exact-port and
   scheme denials, authenticated sessions via both origins, native writes off,
   running/no-autorestart/disabled-autostart unit, exact extra environment,
   unchanged complete Serve config/no Funnel, same historian inode/identity and
   binding, and increasing revision. It records NO login credential/cookie.
7. Independently verify retained protected diagnostics survived and document
   reviewed deployed Git head. Existing sessions revoke on restart; owner logs
   in afresh. Preserve evidence of any failed step rather than masking it.
8. Attach review/merge/deployment evidence, then release the existing final sweep
   t_a87670b9. Owner device enrolment/actual-use judgement still cannot be
   self-attested; no MVP/30-day-start/owner-ready notification from this lane.

Rollback removes only this extra-origin drop-in and deliberately restarts,
restoring loopback-only boundary with tailnet403; preserve all state and unrelated
Serve routes. No Funnel or public exposure operation is needed or permitted.
