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

Phase 2 slice 1 adds a bounded read-only Kanban work-observer library and an
opt-in one-shot acquisition of the approved local board. A05/A06 regression
fixtures distinguish process liveness from progress and task disposition from
attempt exit. The actual board observation is partial (bounded event history).
See `docs/hermes-work.md` for the exact scope, five views, privacy and limitations.

This is not a running monitoring service or operational acceptance. There is no
network listener, HTTP/binary OTLP binding,
renderer, native executor, enable switch or runtime-write route. The controller
position cannot enable writes. Local alarm acknowledgement changes Workshop
records only. No third-party renderer code or new dependency has been adopted.
Durable real-workflow runtime integration, the full Phase 2 gate and renderer
remain downstream; fixture success does not mean the product MVP is ready.

Read the precise contracts and limitations:

- `docs/ingest.md`: supported wire subset, trusted acquisition context, privacy.
- `docs/storage.md`: source watermark, recovery, replay and retention boundaries.
- `docs/source-binding.md`: task permissions, instance identity and SQLite reads.
- `docs/hermes-work.md`: scoped read-only collector and explicit live opt-in.
- `docs/standards.lock`: reference pins, including resolved GenAI repository;
  Development-stability conventions are not a conformance certification.

## Development: install, test, demo

Requires Python 3.11+ and its standard-library `venv` support. Runtime uses only
the standard library. Tests additionally require pytest in an existing approved
Python environment. The verified test environment uses Python 3.11.15 and pytest
9.1.1; the no-pip runtime install/demo/check also work on Python 3.14.7.

From a clean checkout, using the desired Python interpreter:

    python scripts/dev.py install
    python scripts/dev.py demo
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
There are no wall-clock reads, native inputs, file writes or service listeners
inside the demo. The snapshot always says `native_write_enabled: false`.

Run tests using the interpreter which already has approved pytest, NOT the
runtime-only `.venv` created above (that environment intentionally has no pytest):

    python scripts/dev.py test
    python scripts/dev.py test backend/tests/test_source_scope.py -q
    python -m pytest -q
    git diff --check

No dependency installation or update is performed by these commands. If pytest
is missing, choose an existing approved test interpreter, or obtain dependency
approval and quarantine verification separately; do not assume the development
helper downloads it. Tests create synthetic fixture databases only in temporary
paths, never query real Hermes databases. The separate explicitly opted-in
`scripts/observe_work.py --approved-local` command is the live observation path.
The clean-source-copy regression exercises
install, both demo entrypoints, and the test command without inherited PYTHONPATH.

`backend/workshop/api.py` is an in-process facade, not an HTTP server. Its
`authorized` flag is a trusted local input, not network authentication/CSRF.
`SourceBinding.task_scopes` is an explicit local allowlist: empty permits no task
links. Correlation mappings and runtime-instance names are trusted configuration.
Native rows read by the SQLite primitive are not runtime-liveness evidence.
Never point Storage at a native database; its writable file is Workshop-owned.

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
