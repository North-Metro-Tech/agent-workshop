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

The local implementation covers synthetic A01–A04 plus A07/A09 fixtures.
It provides an in-memory reducer, explicit identity correlations, coverage and
availability gating, per-feed freshness, Workshop-local alarms, a local read
facade, and bounded function-level CloudEvents/OTLP JSON observation mapping.
It is not a running monitoring service or operational acceptance.

There is no collector, native database access, network listener, command
executor, renderer or runtime-write route. Local alarm acknowledgement changes
only Workshop's in-memory records. The controller position cannot enable writes.
No new dependencies were installed for this slice.

The binary OTLP/HTTP binding, historian, snapshot/restart recovery, A08/A10
coverage and runnable demo remain later Phase 1 work. No third-party renderer
code has been adopted. See `docs/ingest.md` for the exact supported wire subset,
trusted acquisition context and conservative source-restart reconciliation latch.

## Development

Use an existing Python 3.11+ environment with pytest available. From the root:

    python -m pytest -q
    python -m compileall -q backend
    git diff --check

Verified with Python 3.11.15 and pytest 9.1.1: 182 passing synthetic cases.
Compilation also checked with Python 3.14.7. See `evidence/REVIEW.md` for the
original reducer evidence and `evidence/INGEST_REVIEW.md` for this ingress
slice's real red/green output, boundaries, and review attention areas.

`backend/workshop/api.py` is an in-process facade, not an HTTP server. Its
`authorized` flag must come from a trusted local caller; it is not a substitute
for authentication/CSRF protection in a future network binding. Correlation
mappings are trusted local configuration. Observations passed to the reducer
are already-mapped domain data, not a new public telemetry envelope.

## License

Apache-2.0 for original Workshop code. Third-party notices will be catalogued
separately if components are adopted.
