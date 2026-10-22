# Frontend verification

Uses the approved pinned dependencies already in `package.json`; no React Vite plugin or extra package is needed.

```
npm run typecheck
npm test -- --run
npm run build
```

The backend must serve the `dist` output and `/api/*` on the same loopback origin. The client has no remote API setting, query credential, saved browser projection, synthetic fallback or browser-stored login secret. Login uses an in-memory password submission and an HttpOnly service session cookie. Permission intersection is enforced locally for acknowledgement UI and must also be enforced by the service. Native controls are disconnected.

`generated.ts` is initially a temporary contract mirror; the parent run owns replacing it using the backend schema generator and re-running all gates. Alarm state is read from the fact named `alarm_state`; its exact values are the seven specified operating-state labels. Unknown fact values remain visible and never become actionable.

## Actual-service browser test

The Playwright test is not a mocked frontend demo: it requires an actual running loopback service, a built frontend mounted by that service, and its locally provisioned login secret. Set `WORKSHOP_E2E_URL` (default `http://127.0.0.1:8765`) and `WORKSHOP_E2E_TOKEN` only in the test process environment. Do not prefix secrets with `VITE_`, commit them, place them in URL parameters or pass them in command-line arguments.

Run `npm run test:e2e`. Missing provisioning explicitly skips the actual-service scenario. Missing Playwright browsers is a blocker, not a passing browser check. An already-installed compatible Chromium can be selected with `WORKSHOP_E2E_CHROMIUM` (an absolute executable path); no browser or package installation is performed here. Traces, screenshots and videos are disabled to avoid capturing a login secret/private operational facts.

The scenario exercises cookie login, full snapshot, all scene/DOM facts, keyboard selection, reduced motion, disabled controller/hold, no browser storage, credential-free SSE URL and full-snapshot reacquisition on reload. Unit tests additionally cover immutable validation, injection, alarm states, permission intersection, reset/reconnect/ordering/races and direct rasterized fact equivalence. Native source acquisition and all twelve whole-system scenarios remain the parent run's integration gates, not a claim made by frontend unit fixtures.

Canvas is bounded to 96 figures and an 80-line selected-detail excerpt; all items and all facts remain in the equivalent complete DOM hierarchy. The visual adapter contains no activity timer or upstream runtime code. See root `THIRD_PARTY_NOTICES.md` for the actual immutable visual-module extraction.
