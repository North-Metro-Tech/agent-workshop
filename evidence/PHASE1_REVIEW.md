# Phase 1 / A10 engineering handoff

Implementation slice: `t_dbf6fb11`, branch `feat/a10-phase1-gate`, based on
merged A08/main `59696e9`. Core independently reviews and merges this PR.
This document is engineering QA, not independent approval or MVP acceptance.

## Requested and changed

- Scope collision fixtures across task source instance + board + native ID and
  execution runtime instance + native ID. The same native IDs remain distinct;
  parent identities stay in the configured runtime namespace.
- Explicit immutable `SourceBinding.task_scopes` allowlist shared by CE, mapped
  OTLP and stored snapshot validation. Default denies all task links; rejected
  spoofed batches do not publish reducer/index/cursor changes. CE source must
  match the configured binding; OTLP identity/resource labels cannot change it.
- Storage now rejects reused configured runtime instance ownership, alongside
  its existing source/feed/role uniqueness checks. No identity inference.
- `acquisition.read_table`: synthetic-tested, exact-schema bounded SQLite reads
  with mode=ro + query_only, trusted_schema off, parameterised equality filters,
  fixed row/value/aggregate/VM budgets, short per-call read transaction, reliable
  close and live WAL visibility without immutable mode. Native content/schema
  is unchanged; unknown schema and invalid bounds fail closed.
- Structural interlock tests across ingress/storage/API/acquisition/demo,
  all UI controller positions, authorization states, environment and producer
  flags. No native route, executor, enable switch, listener or runtime write.
- Deterministic synthetic demo, source-only no-pip install, test/demo/check
  helper and README. No dependency change/download; no real Hermes input.

## Red before green

Signed test-first baseline `735bfbe` preserves `evidence/a10-red.txt`:
52 failed, 1 passed before source permissions, reader, demo and dev commands
were implemented. It intentionally predates those interfaces. During first
green iteration, corrected three fixture/compatibility issues: dataclass-key
JSON comparison, PRAGMA recording in its connection test, and Python 3.11's
lack of the newer venv context.lib_path attribute (use sysconfig's venv scheme).
These are recorded here rather than misrepresented as product fixes.

Internal read-only QA then identified that fetchall could materialize all rows
before the aggregate byte check. `evidence/a10-edge-red.txt` pins the concrete
failure (1 failed, 5 passed). Reader now consumes incrementally and closes on
limit failure. Added adversarial exact-extra-schema, BLOB/value/view rejection
and OTLP resource-spoof cases; narrowed WAL claims to native content/schema,
not zero filesystem side effects. Tightened structural allowlist to exact
urllib.parse, not arbitrary urllib submodules. Internal QA does not replace Core.

## Actual execution

Existing approved test interpreter: Python 3.11.15, pytest 9.1.1. No package
installed. Commands from repository root:

    python scripts/dev.py test
    python -m pytest -v -k A01       # repeated for A02/A03/A04/A07/A08/A09/A10
    python -m pytest -v backend/tests/test_phase1_gate.py
    python scripts/dev.py check
    git diff --check

Actual full run: **294 passed in 2.53s**, exit 0 (`evidence/a10-green.txt`).
Actual per-scenario counts and named tests (not disjoint coverage totals):

| Scenario | Green cases | Raw evidence |
| --- | ---: | --- |
| A01 | 8 | phase1-A01.txt |
| A02 | 8 | phase1-A02.txt |
| A03 | 25 | phase1-A03.txt |
| A04 | 25 | phase1-A04.txt |
| A07 | 100 | phase1-A07.txt |
| A08 | 52 | phase1-A08.txt |
| A09 | 16 | phase1-A09.txt |
| A10 | 35 | phase1-A10.txt |

Interlock/dev module: **25 passed**, exit 0 (`phase1-interlock-dev.txt`).
The clean-source-copy regression strips PYTHONPATH, provisions a no-pip venv,
runs both demo entrypoints and runs the original truth-model test module via
the documented helper. It copies no caches, local .venv or native source data.

Manually ran `python3 scripts/dev.py install`, installed `.venv/bin/python -m
workshop.demo`, helper demo, and compile checks with Python 3.14.7. Installed and
helper JSON outputs compare exactly; committed capture is `phase1-demo.json`.
The Python 3.11 check also passes. No static typechecker, coverage percentage,
benchmark or external CI success is claimed. The negative unexpected-config
constructor fixture deliberately passes an invalid keyword; that is not a
production type-check error being hidden. Branch-protection lookup returned
HTTP 403 with this publication identity; exact-head check state is read at PR
handoff, never interpreted as green just because no checks exist.

## Review attention / compatibility

1. Empty task scopes now deny task links. The existing A07 task fixture declares
   its previously implicit permission; legacy stored bindings default empty on
   reopen. Retained facts stay intact, but future links require explicit local
   configuration. Binding runtime values name instances, not a product name.
2. Readonly SQLite is not no-side-effects: live WAL can create/update SHM and
   coordination files. Assertions cover original records/schema/database bytes
   and live database/WAL bytes; no no-locking/zero-sidecar claim. No immutable.
3. This primitive is not a Hermes schema adapter, collector, native pagination
   protocol, complete runtime inventory or trusted atomic A08 watermark. A
   truncated result cannot establish absence/complete coverage. Phase 2 owns
   real approved schema mapping, acquisition evidence and recovery contract.
4. Guard tests and exact import allowlists are regression aids, not a Python
   sandbox. Local callers/configuration remain trusted; no network auth exists.
5. The no-pip install links this checkout; it is not a published wheel or a
   dependency bootstrap. Tests require an already-approved pytest interpreter,
   which is separate from its deliberately runtime-only virtual environment.
6. A08 historian bounds and serial-writer/caller-clock constraints still apply.
   GenAI reference remains the resolved supplied revision in the dedicated
   semantic-conventions-genai repository, Development stability, not certified.
7. `RESUME.md` is a shared Core/coder hotspot. Preserve Core's post-A08 history
   and write the A10 handoff serially. No protected project instruction edits.

Claude Code CLI was absent from PATH and standard installation locations;
implementation used the explicitly allowed direct fallback. No harness install,
provider, profile, credential, dependencies or unrelated files were changed.
No renderer/live integration/HTTP/binary OTLP service, real data or operational
acceptance is included. No auto-merge: Core owns independent review and merge.
After merge, Phase 1 is accepted and Core routes the Phase 2/MVP work. Do not
complete the downstream MVP gate or notify the owner that the MVP is ready.
