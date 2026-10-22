# Release 1 bounded historian: implementation handoff

Task: t_127a054a. Status: IMPLEMENTATION COMPLETE; independent approval NOT granted.
Base: feat/phase3-mvp at 35e8c334c4d1dc01f32d0cddd62edec0e64ea9b1 exactly.
Candidate branch: fix/release1-bounded-historian. Intended PR base: feat/phase3-mvp.
Publication: LOCAL ONLY, per completion contract and downstream review protocol.
No remote push, PR, merge, auto-merge, external CI success or deployment claim.
The deliverable archive contains an SSH-signed incremental Git bundle against the
exact base, plus a handoff recording its final head and checksums. No installed
checkout or preserved historian is modified to publish this branch.

## Engineering outcome

Replaced every-revision full-state snapshots with changes-only revisions and
32-revision full anchors. Promote the oldest survivor to an anchor atomically
before removing its predecessor. Keep the existing closed data-only codec,
transaction/recovery/cursor APIs and bounded source journal. Domain tables still
use straightforward replacements; this is not a constant-cost write-path claim.

Added count-based insertion-order retirement:

- 64 observations per execution, preserving first, lifecycle/native/mapping/
  authority transitions, distinct terminal facts and discrepancy-linked facts.
  Only redundant same-lifecycle observations are eligible; exact identical
  terminal facts remain represented once. Original indices survive retirement.
- 256 safe metadata records per Ingest, oldest unprotected first. Preserve
  material domain assertions, process/task/station/outcome changes, trace/span/
  resource/scope correlations, and original acquisition provenance. This applies
  even to unchanged lifecycle and corroboration-only records. Safe validated
  domain fields are retained, never arbitrary producer content.
- 512 dedup identities per Ingest, insertion-order eviction (not retry-refreshed
  LRU). A retained identity still rejects changed digests. After eviction,
  EXACT first-sighting validation/ordering/scope/epoch/terminal/cursor semantics
  apply; its digest is then retained again. No silent collision tombstone.

Neither clocks nor acquisition times are rewritten. Stable diagnostic IDs use
original observation indices; the HTTP excerpt remains limited to 100. Internal
retention fields are excluded from the public LocalAPI projection. Collector,
service, native adapter, source scope, controls, manifests and locks are unchanged.
A narrow exact-file interlock entry permits stdlib difflib in delta.py only; no
network, execution, clock capability or broad import permission was added.

## Explicit capacity/recovery limits (review attention required)

A count cap cannot both accept arbitrarily many distinct protected facts and
preserve them all. If a per-execution/per-source capacity has only protected
entries, RetentionCapacityError rejects the ENTIRE staged transaction. It does
NOT drop terminal/conflict/audit/correlation/discrepancy evidence. Feed clocks,
source cursors, ordering, dedup state and revisions roll back. Repeated retries
or restarts do not resolve that capacity: explicit owner-reviewed disposition is
required. This operational limit was flagged on the task before implementation
and is tested, not silently hidden as a whole-domain disk quota.

Distinct executions/correlations/ambiguities/alarm audit and ordering/retired
source epochs are not retired. No fixed quota is claimed for an arbitrarily
growing protected domain. The tests bound bytes for fixed-cardinality redundant
acquisition streams; they do not establish 30-day/fleet throughput, RSS behavior,
physical shrink/vacuum, backup or hostile-local-user/multiwriter guarantees.

Schema version 2 is fresh-historian-only. Version 1 is rejected BEFORE WAL,
schema or data changes; byte-for-byte preservation is tested on a legacy-shaped
fixture. No migration/prune/overwrite/restart touches the preserved ~1.9GB
installation historian. Rollback/recovery uses a separately chosen historian
matching the product version, preserving old state and mode/boot sidecars.
A normal version-2 service restart still deliberately commits a new freshness/
coverage invalidation revision; retained historical projections are unchanged.

## Actual validation

All commands run in the isolated task checkout, synthetic only. No live source
acquisition, fleet install, service restart of the installed unit, or native
writes. Backend interpreter: /home/aaron/hermes-agent/.venv/bin/python (3.11.15).
The implementation harness Claude Code was absent from PATH and normal install
locations; the documented direct fallback was recorded on the card. Internal
Lead/subagent QA is NOT independent approval.

Current complete suite:

- backend-attempt3.txt: python -m pytest -v -s: 494 PASSED, ZERO SKIPS
  (all 472 existing tests plus 22 added). Includes default-policy sustained
  acquisition, retained-window replay equality, restart invalidation equality,
  eviction/collision/first-sighting equivalence, terminal/discrepancy/audit/
  correlation survival, metadata process/span transitions, ignored terminal
  assertion provenance, capacity rollback, snapshot path and data-codec tests.
  Retention windows 2,8,33,128 also prove no-op deltas do not copy unchanged
  audit and every retained window starts with an anchor.
- frontend-attempt1.txt: npm run typecheck; npm test -- --run; npm run build:
  57 PASSED, ZERO SKIPS; typecheck and build succeeded.
- browser-attempt1.txt: four real Chromium/actual TCP synthetic service tests
  PASSED, ZERO SKIPS: scene/DOM/keyboard/fixed-off authority, transport reconnect,
  new browser/service restart/session revocation/history and local acknowledgement.
  Used the existing exact-lock runtime Python and existing Chromium. The test
  provisions isolated synthetic state/random secret and stops its own service.
  browser-scene.png is raw browser output, not a qualitative visual approval.
- schema-attempt1.txt: scripts/generate_schema.py --check succeeded.
- demo-attempt1.txt, collector-demo-attempt1.txt, compile-attempt1.txt:
  scripts/dev.py demo, collector-demo, check all succeeded.
- Dependency manifests/locks and service/collector implementations have empty
  diffs. No package was added/installed/downloaded. Frontend node_modules was
  copied into this task from the existing installed cache ONLY AFTER its
  package-lock.json matched SHA256
  38cc42069447d1ba1cd9324953d98f7620b3817c2f9642b1fefb673266359d0c.
  No new quarantine/audit or independent clean-install claim is made.

Default-policy regression (backend-attempt3.txt), 360 cycles/1,080 synthetic
new identities, one active + two unchanged terminal execution identities:

  cycle   state bytes  revision payload bytes  DB+WAL+SHM allocated bytes
    180       241962                 1762448                     7057408
    270       242271                 2007094                     7532544
    360       242271                 2029323                     7720960

All three samples retain exactly 128 revisions, five anchors, 64 active-execution
observations, 256 metadata records and 512 seen identities. Assertions require
state <512KiB, revisions+events <8MiB, allocation <32MiB, bounded post-saturation
variation. Counts/bytes, NOT wall-clock rate, are the acceptance assertions.
All 128 retained projections equal their captured snapshots; restart preserves
old projections and produces exactly the documented invalidated current view.
All original terminal facts/acquisition metadata survive; no RSS extrapolation.

## Same-probe red/green evidence

Run growth_probe.py from the target root with PYTHONPATH=backend:collectors,
passing a NONEXISTENT synthetic historian path. It performs 180 cycles with two
fixed execution identities, never imports or acquires native sources.

- growth-base-red.txt: exact base exported into a separate task-local directory;
  actual exit 1, EXPECTED RED. Retained revision payload 21,754,623 bytes exceeds
  the identical 8MiB assertion; 360 observations/360 metadata, 128 revisions.
- growth-candidate-green.txt: actual exit 0. Revision payload 1,257,078 bytes,
  65 observations (64 active + one terminal), 256 metadata, 128 revisions,
  allocated historian 6,324,224 bytes. Same inputs and assertions, no relabelling.
- These are synthetic comparison measurements, NOT installed-fleet predictions.

## Failed QA attempts preserved honestly

- backend-attempt1.txt: existing-suite candidate attempt failed because new
  stdlib difflib was not yet allowed by the exact-file import interlock. Added
  only the pure-data module's narrow entry; broad boundary unchanged.
- retention-attempt1.txt: 13 passed/one failed; failed assertion compared alarm
  controller objects by identity rather than serialized state. Fixed the QA
  comparison to the closed codec; no product gate was bypassed.
- retention-attempt2.txt: all 18 initial new tests passed, including added
  material metadata protections after internal QA caught an early preservation
  gap (process/correlation changes with unchanged lifecycle). Those early changes
  were never submitted/approved as safe; final protections and regression tests
  are part of this candidate.
- backend-attempt2.txt: 490 passed, zero skips, before adding four no-op/anchor
  window cases. Preserved as that actual earlier pass, not the final test count.
- anchor-windows-attempt1.txt: three passed/one failed in test setup semantics:
  retention=128 still included revision 2, which legitimately CREATES the audit,
  unlike subsequent no-op revisions. Scoped the no-op assertion to revisions
  after 2; the final full 494 run above passes. No product fix was required.

Raw transcripts remain unchanged, including failures and elapsed times. Scoped
.gitattributes excludes raw .txt whitespace only; no test skip/waiver is added.

## Independent review and release handoff

Review t_aa215edd must independently audit the exact signed head and rerun gates;
then t_41c8ebed must perform sustained resource/recovery QA. Both remain installer
prerequisites. t_2ec73616 cannot deploy from implementation completion alone.
The task body mentions same-card request_review, but the pre-created review
child is the actual encoded lane: completing THIS implementation task releases
that child, without a duplicate same-card review or stranded dependency.

Before installation, review capacity-exhaustion behavior and fresh-schema
recovery explicitly. No approval/merge/deployment, Appendix A expansion,
exhaustion prediction, mount-hardening proof, owner-use readiness or owner-ready
notification is provided by this implementation. Existing final gates remain.
