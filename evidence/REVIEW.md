# A01–A04 implementation evidence and review handoff

## Objective and approach

Implement only the first truth-model reducer slice using synthetic fixtures.
The domain layer uses Python dataclasses and explicit acquisition times; there
are no external runtime dependencies. It performs no network or database I/O.

- A01: concurrent execution/session/parent/composite task identity; explicit
  versioned alias correlation; visible ambiguity and conflicting provenance.
- A02: registered versus observed roles; incomplete inventory and partial
  scopes; retained native/mapped/source/version/quality values.
- A03: fresh complete scope reconciliation, admission, reachability and usable
  capacity required for available; observed executions remain distinct; idle
  is not a fault. Native writes have no route, executor or enable switch.
- A04: per-feed and per-field acquisition deadlines, configurable feed policy,
  stale/lost indication independent of transport traffic; rationalised alarm
  occurrences, acknowledgement, clear-before-ack, recurrence, grouped root
  incidents, first-out uncertainty, delays, shelving/expiry, suppression and
  explicit maintenance removal. Condition and acknowledgement survive controls.

## Executed evidence

Python 3.11.15, pytest 9.1.1, existing environment; no installs or upgrades.

1. `python -m pytest -q --tb=no` against executable red skeleton:
   `42 failed in 0.05s`, exit 1. Exact output: `a01-a04-red.txt`.
   The tests and skeleton are preserved in signed commit `d326ea5`.
   Skeleton methods deliberately raise NotImplementedError; they are replaced
   by real implementations in the final branch. This is not a production stub.
2. Initial implementation: 42 cases passed. Adversarial review then added
   regressions for authority retention, unsupported terminal mappings and
   unverified availability evidence: `5 failed, 14 passed in 0.06s`, exit 1.
   Exact assertion output: `a01-a04-edge-red.txt`. All five failing cases now pass.
3. Cross-role identity-conflict regression: `1 failed, 65 deselected in 0.05s`,
   exit 1. Exact output: `a01-cross-role-red.txt`. Disputes now block available
   for both roles rather than making one role appear empty.
4. Final full suite: `66 passed in 0.05s`, exit 0.
   Exact output: `a01-a04-green.txt`.
5. `python -m compileall -q backend`: exit 0.
6. `git diff --check`: exit 0.

The evidence files are actual captured stdout/stderr, not reconstructed test
results. The appended PYTEST_EXIT_CODE records pytest's own pipeline status.
There is no coverage-percentage claim: coverage, ruff and pyright CLIs were not
available in the selected environment. Compilation is not a type check.

## Review attention and deliberate boundaries

Review explicit identity mapping, availability evidence classes, field-level
freshness (including shared feeds), and alarm incident/occurrence separation.
Tests are synthetic; no live telemetry, native database or frontend was used.

The reducer is a trusted local domain interface, not an ingest validator.
Source binding, redaction, CloudEvents/OTLP, stable native ordering, paginated
snapshot races, persisted historian/restart recovery and full source-authority
repair belong to the remaining Phase 1 cards. No A07–A10 completion is claimed.
A conflicting identity remains conservatively disputed; this slice deliberately
has no arbitrary conflict-clear action. Historical alarm records and audit are
in memory, not a durable historian. A feed-loss alarm is enabled only after an
explicit rationalisation and is evaluated when the local caller invokes tick.
Clock/order uncertainty is retained rather than claimed as physical causality.

The local API has no HTTP listener and no native command callback. Only its
trusted-caller alarm-acknowledgement operation mutates Workshop-local state.
Production session/origin/CSRF security must be implemented in the later HTTP
binding; a boolean supplied by a remote caller must never be trusted as auth.

## Delivery status

Branch: `feat/a01-a04-truth-reducer`.
Implementation was performed directly because the Claude Code executable was
unavailable; this is the documented delegation-infrastructure exception. No
provider/model/profile configuration or credentials were changed.

Core's updated handoff resolves the authorised destination to
`North-Metro-Tech/agent-workshop`, superseding the older namespace on the card;
origin already points there. Both GraphQL and git cannot resolve that target.
Core records remote provisioning as an owner action. The earlier attempt to
create the old `vitruvius-nmt` target returned HTTP 403; no credential changes
or further provisioning attempts were made. No push to main was attempted.
No PR URL or CI result exists to report. Publication and independent-review
handoff require owner provisioning/access; local green tests do not waive it.

Coordination hotspot: `RESUME.md`. Core's bootstrap/handoff commits landed in
this shared workspace during implementation. The guarded writer detected the
second edit, and the final handoff preserves Core's corrected destination.
