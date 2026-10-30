# Phase 3 progress — frontend only, gate remains OPEN

This is an intermediate development checkpoint, NOT MVP readiness or a deployable
service. The owner-notification gate `t_7e8a8223` must remain incomplete.

## Implemented and independently exercised

- React/TypeScript immutable projection client and specified `src/workshop/`
  modules: scene adapter, stationary original pixel figures, roster, faceplate,
  review bench, attention rail, timeline and local operator panel.
- Shared source facts for canvas and equivalent keyboard-accessible DOM; explicit
  partial-coverage disclaimer, native/mapped/age/source/evidence details, persistent
  task figures supplied independently of execution figures, read-only controller,
  permanently disabled non-safety-rated admission hold, reduced-motion handling.
- Browser transport requests same-origin session cookies and CSRF; no token or
  cursor in URLs/storage. Full snapshot recovery on reconnect and cursor identity
  changes, race/old-revision/disconnect guards. These are CLIENT tests against
  mocks, not evidence that server-side authentication or SSE exists.
- Narrow visual extraction from immutable Pixel Agents source, with MIT notice
  in `THIRD_PARTY_NOTICES.md`. Upstream geometry and opaque-pixel raster loop
  independently read again before this checkpoint. No upstream server, runtime
  heuristics, hooks, PTY, assets or controls imported.

Parent independently ran `npm run typecheck`, `npm run test -- --run
--reporter=verbose`, `npm run build`, and `npm audit --include=dev
--audit-level=low`: 47 tests pass; typecheck/build pass; audit reports zero
vulnerabilities. Existing backend suite independently rerun: 432 pass. Raw
outputs are `evidence/phase3-frontend-*.txt`, `phase3-backend-baseline.txt`, and
`phase3-socket-ci.txt`. Socket-wrapped `ci` used `--ignore-scripts --include=dev`
and a seven-day date cutoff. Exact direct pins and all resolutions are committed
in `frontend/package*.json`. All 99 unique name/version resolutions, including
optional platform packages, passed authoritative registry publication-age,
integrity and tarball checks; evidence and reproducible standard-library checker
are `evidence/phase3-npm-quarantine.json` and `scripts/check_npm_quarantine.py`.
This age/integrity check is not a security audit or a conformance claim.

## Explicit outstanding work

- No HTTP/SSE service, server-side authentication/authorization, serial writer
  binding, timer, session/CSRF/Host/Origin enforcement or static deployment yet.
- `frontend/src/workshop/generated.ts` is explicitly a TEMPORARY contract mirror,
  NOT generated from Pydantic. Replace it from actual backend schema before
  integration or acceptance. Client fact schema is not the native telemetry wire
  envelope; continue using established ingress/reducer contracts.
- `frontend/e2e/workshop.spec.ts` is an unexecuted actual-service test. It skips
  without a provisioned service/token. No browser/Playwright run, screenshot,
  live service, real-fleet HMI or A23 operational acceptance claimed.
- No new twelve-scenario acceptance claim. Previously accepted Phase 1/2 raw
  evidence remains historical; final scenario files must include real integration
  evidence and name pinning tests. No forced/destructive live workflow variants.
- No native reads/writes, live installation, daemon, source discovery, provider,
  profile, credential or security changes in this frontend checkpoint.
- No independent review, PR approval, merge or release acceptance yet. Claude
  Code remains absent; documented direct fallback and bounded delegated frontend
  work were used, with parent independently rerunning the gates.

## Narrow authorization gate discovered before backend adoption

The approved architecture names FastAPI/Pydantic; the task's additional package
ruling explicitly allowlists the frontend toolchain and its audited transitives.
A maintained ASGI server is still needed for actual same-origin HTTP/SSE serving.
Uvicorn is installed in the host harness, but using that incidental installation
as an undeclared product dependency would not create a reproducible clean-checkout
service or meet the dependency freeze. It has not been added, installed, pinned
or used to launch this product. Request a task-scoped allowance for `uvicorn`
(minimal non-`standard` distribution; no extras), plus only necessary audited
runtime transitives, with exact pins, committed Python lock/hashes and seven-day
quarantine unchanged. Also explicitly confirm necessary runtime transitives of
the already-selected FastAPI/Pydantic stack in that lock. No requested age
exception. Do not invent an ASGI server or borrow the harness environment to
bypass the freeze.

Once Core/PO rules: resolve/check the Python lock, implement the serial service
and schema generator, server security/recovery tests, actual-service browser
checks, final scenario evidence, independent review and authorized installation
against ONLY the previously approved `agent-workshop` source/scope. Runtime
coverage remains partial and availability unknown; no atomic runtime watermark
exists. Keep completion LAST and preserve the sole owner notification point.
