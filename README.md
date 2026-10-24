# Agent Workshop

A supervisory layer and control-room HMI for LLM-driven actors, built with
control-systems engineering: ISA-101 HMI principles, ISA-18.2-aligned alarm
states, and reconciliation-gated availability.

Operators see who is executing what, the age and quality of that information,
blocked work, dependencies and review outcomes — then drill into evidence.
Animation and model narration are never treated as progress.

Hermes is adapter one. Release 1 is read-only: Workshop observes agent runtimes;
it does not control them.

## Status and scope

Phase 1 implementation covers synthetic A01–A04 and A07–A10 fixtures: truth
reducer, scoped identities, coverage/availability, freshness, Workshop-local
alarms, function-level CloudEvents/OTLP JSON ingress, Workshop-owned SQLite WAL
historian, atomic snapshot/restart/replay recovery, scoped task-link permissions,
bounded read-only SQLite primitive, and runnable synthetic demo.

Phase 2 integrates bounded read-only work/runtime observers, scoped durable
correlation, and a bounded crash-recoverable observation outbox on the approved
local board. A05/A06/A08/A10/A25 have named regression evidence, and an explicit
opt-in workflow command compares actual acquired native facts to projections.
Source event history and runtime coverage are plainly partial. Forced-transition,
crash and uninstall/schedule variants remain isolated, not fabricated live
transitions. See `docs/phase2-workflow.md` and `evidence/PHASE2_REVIEW.md`; Core
independent review/merge is the Phase 2 acceptance gate.

The Phase 3 remediation adds a loopback-only HTTP/SSE binding and a built
React canvas/DOM HMI. This remains a development service, not operational/MVP
acceptance. There is no native executor, enable switch or runtime-write route;
controller cannot enable writes. Workshop-local acknowledgement changes only
Workshop records. Frontend visual extraction attribution is in THIRD_PARTY_NOTICES.md.

## Start the loopback HMI (Phase 3)

Use Python 3.11+ and Node with the approved toolchain. The pure domain/demo stays
standard-library-only. The serving layer additionally requires the exact approved
runtime lock. Install commands must run through Socket Firewall; no extra packages,
Uvicorn standard extras, public bind, reload, or multiple workers are supported.

    python3 scripts/dev.py install
    python3 scripts/check_python_lock.py
    sfw uv pip install --python .venv/bin/python --require-hashes --only-binary :all: --exclude-newer 2026-10-15T00:00:00Z -r requirements.lock
    python3 scripts/check_npm_quarantine.py
    cd frontend
    sfw npm ci --include=dev
    npm audit
    npm run typecheck
    npm run build
    cd ..
    .venv/bin/python scripts/dev.py schema --check
    .venv/bin/python scripts/dev.py serve --synthetic --init-secret
    .venv/bin/python scripts/dev.py serve --synthetic

Open http://127.0.0.1:8765 exactly (localhost is a different authority). Enter the
private secret from .workshop-state/service/synthetic/login-secret into the login
form; never place it in a URL, VITE variable, bundle, browser storage or evidence.
The init command creates a mode-600 file and never prints its contents. A provisioned
WORKSHOP_LOGIN_TOKEN environment variable can instead supply a distinct 32+ character
secret in the server process only. Session cookies are HttpOnly/SameSite Strict,
loopback HTTP (not Secure/TLS); session and CSRF authority expires after one hour
and is revoked by process restart. This is not protection from a hostile local OS
user or same-origin XSS. Do not reverse-proxy, tunnel or expose this service
except for the single owner-authorised tailnet-only origin documented in
`OPERATOR.md` (24 October 2026). `WORKSHOP_EXTRA_ORIGIN` is optional and must be
one exact HTTPS `.ts.net` origin; omission preserves the loopback-only boundary.
This is not a wildcard allowance or public/Funnel authorisation.

Explicit --approved-local instead of --synthetic uses only the already-approved
agent-workshop board/runtime scope. It is opt-in live read-only acquisition; no
native controls. It uses separate state and requires its own init-secret invocation.
No live collection is performed by install, test, schema or synthetic serve.
The single event loop owns every SQLite access; a lifetime advisory writer lock
rejects a second service before opening Storage. Keep all other writers away from
the service historian. Source mode and Linux boot clock identity are fenced in a
sidecar: process restart preserves diagnostics but invalidates live acquisition;
a host reboot requires explicit new state/recovery, never reuse old monotonic ages.
Do not delete the sidecar to bypass a recovery failure. No service autostart is installed.

The committed generated.ts and docs/web-schema.json are generated from backend
Pydantic models by scripts/generate_schema.py. Regenerate with dev.py schema;
--check fails on drift. They are not a handwritten TypeScript contract mirror.
History is a bounded historian-backed excerpt with stable identity/provenance,
not snapshot receipts or current state. Observations without retained acquisition
timestamps say so explicitly. No transcript or native filesystem browser is served.

The version-2 historian uses changes-only revisions with 32-revision anchors and
deterministic retirement of redundant observations/metadata/dedup identities.
Existing version-1 historians are rejected without mutation: keep them preserved
and use an explicitly chosen fresh separate historian after the release gates.
Protected evidence is never silently pruned; capacity exhaustion rejects the
whole acquisition transaction. Read `docs/storage.md` for exact limits, dedup
first-sighting-after-eviction semantics and the owner-reviewed recovery boundary.
This is not a whole-domain byte quota or an installed-fleet/30-day capacity claim.

After building, npm --prefix frontend run test:e2e provisions its own isolated
synthetic TCP service, random secret and historian. There are no service-dependent
skips. Existing audited Chromium can be selected with WORKSHOP_E2E_CHROMIUM; this
command does not download a browser. It tests real canvas/DOM facts, transport
reconnect, a new browser process, service restart, retained history and local ack.
Manual screen-reader/assistive-technology speech has not been verified: live-region
DOM, transition deduplication, focus preservation and reduced-motion are automated
coverage only. Clean-checkout QA and twelve-scenario reruns remain downstream gates.

The lock was resolved for Linux x86_64 / Python 3.11; that is the verified serving
environment. The explicit installation cutoff matches its recorded resolution,
is over seven days old, and avoids an unrelated user's stricter uv default making
the exact lock unsatisfiable. The metadata/hash/OSV quarantine check is still
mandatory before installation; this cutoff is not an age exception. Every Python
resolution, including transitives, is pinned and hashed. Do not resolve additional
platform dependencies without a fresh allowance/quarantine/security check.

Read the precise contracts and limitations:

- `docs/ingest.md`: supported wire subset, trusted acquisition context, privacy.
- `docs/storage.md`: source watermark, recovery, replay and retention boundaries.
- `docs/source-binding.md`: task permissions, instance identity and SQLite reads.
- `docs/hermes-work.md`: scoped read-only collector and explicit live opt-in.
- `docs/hermes-runtime.md`: lifecycle authority, correlation and restart contracts.
- `docs/phase2-workflow.md`: outbox bounds/recovery, collector demo and gate limits.
- `docs/standards.lock`: reference pins, including resolved GenAI repository;
  Development-stability conventions are not a conformance certification.

## Development: install, test, demo

Requires Python 3.11+ and its standard-library `venv` support. Domain/demo runtime
uses only the standard library; HTTP serving requires the lock above. Tests
additionally require pytest in an existing approved
Python environment. The verified test environment uses Python 3.11.15 and pytest
9.1.1; the no-pip runtime install/demo/check also work on Python 3.14.7.

From a clean checkout, using the desired Python interpreter:

    python scripts/dev.py install
    python scripts/dev.py demo
    python scripts/dev.py collector-demo
    python scripts/dev.py check

Install creates `.venv` without pip or third-party downloads and links only this
checkout's backend and collectors through a `.pth` file. It refuses an existing unmanaged
`.venv`; it does not overwrite another environment. This is a source-checkout
install, not a distributable wheel; moving the checkout requires reinstalling.
You can also run the installed demo directly without PYTHONPATH:

    .venv/bin/python -m workshop.demo

Demo prints deterministic JSON to stdout; redirect it to a file if desired:

    python scripts/dev.py demo > snapshot.json

It seeds synthetic instances/boards with colliding native IDs, active roles,
an available idle role and an unobserved role whose availability stays unknown.
The Phase 1 `demo` has no wall-clock reads, native inputs, file writes or service
listeners. The separate `collector-demo` exercises temporary synthetic SQLite
files through the collector/outbox/OTLP/historian path, labels all samples
synthetic, and performs no live acquisition or service binding. Both always say
`native_write_enabled: false`.

Run tests using the interpreter which already has approved pytest, NOT the
runtime-only `.venv` created above (that environment intentionally has no pytest):

    python scripts/dev.py test
    python scripts/dev.py test backend/tests/test_source_scope.py -q
    python -m pytest -q
    git diff --check

The service tests additionally require the exact runtime lock. With the verified
Python 3.11 runtime-only `.venv` and a separate existing approved Python 3.11 pytest
interpreter, use (set APPROVED_TEST_PYTHON to that interpreter's absolute path):

    PYTHONPATH=.venv/lib/python3.11/site-packages:backend:collectors "$APPROVED_TEST_PYTHON" -m pytest -q

This does not install pytest or use an incidental harness FastAPI/Pydantic version.
Alternatively use an already-approved test environment containing both pytest and
the exact runtime pins. A missing pytest is not a product test pass.

No dependency installation or update is performed by these commands. If pytest
is missing, choose an existing approved test interpreter, or obtain dependency
approval and quarantine verification separately; do not assume the development
helper downloads it. Tests create synthetic fixture databases only in temporary
paths, never query real Hermes databases. The separate explicitly opted-in
`scripts/observe_work.py --approved-local` command observes the work surfaces;
`scripts/observe_workflow.py --approved-local` exercises the integrated live path.
The clean-source-copy regression exercises
install, both demo entrypoints, and the test command without inherited PYTHONPATH.

`backend/workshop/api.py` is an in-process facade, not an HTTP server. Its
`authorized` flag is a trusted local input, not network authentication/CSRF.
`SourceBinding.task_scopes` is an explicit local allowlist: empty permits no task
links. Correlation mappings and runtime-instance names are trusted configuration.
Native rows read by the SQLite primitive are not runtime-liveness evidence.
Never point Storage at a native database; its writable file is Workshop-owned.

## Runtime correlation (Phase 2 slice 2)

`collectors/workshop_collectors/hermes_runtime.py` maps the approved native
attempts through scoped OTLP ingestion into the separate Workshop historian.
Process liveness is independent corroboration; lifecycle retains the trusted
`source_record` evidence class. No atomic runtime watermark is fabricated from
the board cursor and later process samples; runtime coverage stays partial and
reopening the historian cannot establish availability from disk.

Explicit opt-in only: `python3 scripts/observe_runtime.py --approved-local`.
This writes only git-ignored `.workshop-state/` and prints redacted live evidence.
Normal install/test/demo/check commands never read the live board. Details,
caller-owned stream sequence/epoch, source identity fence and actual-vs-fixture
A25 limits: `docs/hermes-runtime.md` and `evidence/HERMES_RUNTIME_REVIEW.md`.
`observe_workflow.py --approved-local` additionally uses a bounded durable
outbox and verifies same-acquisition native/projection agreement. It writes only
Workshop-owned git-ignored state. A25 removal/restore and schedule invariants
remain isolated deployment evidence, not shared-live destructive operations.

## Evidence

`evidence/PHASE1_REVIEW.md` maps the closing slice and its actual red/green output.
`evidence/REVIEW.md`, `INGEST_REVIEW.md`, and `STORAGE_REVIEW.md` preserve the prior
implementation slices' evidence and limitations. Per-scenario `phase1-A*.txt`
captures name the fixture tests for A01–A04 and A07–A10. These synthetic results
are not live-fleet, frontend, standards-conformance or certification claims.
Core independently reviews and merges the feature PR before Phase 1 is accepted.

## License

Apache-2.0 for original Workshop code. Third-party notices will be catalogued
separately if components are adopted.
