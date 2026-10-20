# A07/A09 ingress evidence and review handoff

## Requested / implemented

Function-level standards ingress on the merged A01–A04 reducer, using only
synthetic fixtures. No network listener, live integration, renderer, source
writes, dependency adoption, model/profile changes or credentials work.

- CloudEvents 1.0.2 reference, `specversion=1.0`, existing structured JSON/batch
  shape, minimal required context + versioned execution-lifecycle data schema.
- OTLP native JSON export shapes for traces/logs, configured source scope,
  explicit native identity, resource/scope/schema and trace/span correlation.
  Completed spans are terminal/corroborating evidence, never live inventory;
  unidentified lifecycle logs cannot create actors or replace inventory.
- Application idempotency and changed-content rejection; known native revision
  ordering, otherwise original acquisition ordering; immutable completed-span
  merge policy; stable actor identity shared by both protocols.
- Distinct source occurrence, source-observed, original acquisition and service
  receipt times. Missing/skewed capture remains unknown, offline backlog does
  not gain freshness on arrival, collector epoch changes invalidate old live
  evidence even when the first new-epoch record is an exact retry.
- Bounded parsing, privacy allowlist and all-or-nothing in-memory batches.

Small domain changes are necessary, not unrelated refactoring: Observation and
Execution can represent unknown timestamps; the local facade emits unknown age
rather than crashing. Late acquisitions retain their original per-field time
without rewinding a feed. The internal source_ordered flag admits only ingress-
validated within-source ordering; terminal and cross-authority safeguards remain.

## Executed evidence

Existing Python 3.11.15 environment, pytest 9.1.1. No packages installed. The
active default Python 3.14.7 has no pytest; using the pre-existing test environment
avoids an unnecessary dependency install.

1. Original reducer baseline independently executed: `66 passed in 0.05s`.
2. Tests written before implementation; executable red skeleton and 83 failing
   ingress tests preserved in SSH-signed commit `7436aae`:
   `83 failed in 0.59s`, exit 1. Exact output: `a07-a09-red.txt`.
   The skeleton raises NotImplementedError; final code replaces every stub.
3. Adversarial QA captured `17 failed, 3 passed in 0.15s`, exit 1, before fixing
   restart-on-duplicate, unknown-age snapshots, native revision precedence,
   unfinished/completed span identity, and malformed context/AnyValue handling.
   Exact output: `a07-a09-edge-red.txt`.
4. Second QA capture: `4 failed, 27 passed in 0.12s`, exit 1. Fixed valid standard
   GenAI spans without a domain session being rejected, source-observed log time
   loss, and terminal facts with unknown acquisition being hidden by ordering.
   Exact output: `a07-a09-provenance-red.txt`.
5. Final metadata privacy regression capture: `2 failed, 31 deselected in 0.05s`,
   exit 1. Scope name/version no longer accept arbitrary nested content.
   Exact output: `a07-a09-metadata-red.txt`.
6. Final full suite: `182 passed in 0.16s`, exit 0, including the original 66.
   Exact stdout/stderr: `a07-a09-green.txt`.
   Ingress-only independent command: `116 passed in 0.12s`, exit 0.
7. `python -m compileall -q backend` executed successfully with both Python
   3.11.15 and 3.14.7. `git diff --check` passed.
   Full PR-base check also passed: `git diff origin/main...HEAD --check`.
   `.gitattributes` disables whitespace lint only for raw red captures, whose
   pytest assertion output includes trailing spaces; source code keeps normal
   whitespace checks. No captured evidence was rewritten to conceal whitespace.

All evidence is actual captured output, not generated/reconstructed results.
The PYTEST_EXIT_CODE footer captures pytest's pipeline status. The initial
malformed-byte-array parameter IDs made the red capture verbose; the later test
labels are bounded/readable. One test-only comparator was corrected to compare
alarm state, not deepcopy object identity. No type-check, coverage-percentage,
external runtime, HTTP or protobuf-binary interoperability result is claimed.

## Standards and explicit limitations

See `docs/standards.lock` and `docs/ingest.md` for the supported subset and
source/reference verification. CE and OTLP immutable tag references were read
and resolved through GitHub. The supplied GenAI SHA
`547934afa90a34298441caf80c43b27255c3a292` could not be resolved at the upstream
semantic-conventions repository (HTTP 422); it is retained exactly, not replaced
or represented as verified. Core should confirm that reference at review.

The OTLP mapper consumes standard OTLP JSON, not a substitute envelope. This
function-level slice does NOT implement a binary-protobuf codec or install an
SDK. A future HTTP/protobuf binding must use approved maintained definitions and
pin its SDK compatibility. No HTTP status codes/routes or auth/session claims
are introduced here. Existing PR #1 HTTP advisories remain later work.

State/indexes are in memory and grow with history; this is not a durable/bounded
historian or outbox. Per-call byte/count/depth limits are enforced independently.
Provision one Ingest per source/scope and a dedicated registered feed for it;
serialize calls. Stable log cursors must be unique across native epoch resets.
The source_restart reconciliation latch deliberately cannot be cleared by events;
complete-scope snapshot recovery is the next Phase 1 slice. Partial coverage is
not repaired or invented here. No A08/A10/full Phase 1 completion is claimed.

## Reviewer attention / delivery

Review acquisition-clock trust boundaries, source_ordered authority, terminal
and conflict retention, epoch invalidation (including duplicates), log/span
identity, batch rollback and redaction before retention. In particular evaluate
the explicitly bounded JSON mapping scope versus the later binary binding.

Implementation was performed directly because Claude Code remained absent from
PATH and its standard install locations (same fallback as the first slice).
This was not independent review. Core owns review and merge, as specified in
this card. No auto-merge has been enabled by the implementer.

Branch: `feat/a07-a09-wire-ingest`, based on merged PR #1 at `9f8e876`.
Coordination hotspot: `RESUME.md` — shared Core/coder handoff; updates serialized.
The exact PR URL and head SHA are supplied on the task's lifecycle handoff after
publication and read-back verification, rather than guessed here.
