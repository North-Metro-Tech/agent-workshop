# A10 source binding and SQLite acquisition boundary

## Identity and permissions

`SourceBinding` is trusted, local configuration. Select it using the local
adapter's identity, never a producer's `source`, resource attributes, agent ID,
display name or telemetry-provided principal. Function-level entrypoints are
not authentication or a network endpoint. A future transport must authenticate
its caller and select its binding before invoking them.

Each runtime value names one source instance, not a runtime product name.
Use distinct configured runtime values across instances. `Storage` rejects
reused runtime/source/feed/role owners; do not construct conflicting standalone
Ingest objects sharing a reducer. Deliberate aliases still require the reducer's
explicit versioned local correlation mapping. Parent execution keys inherit
the configured runtime; sessions do not merge executions. Task keys retain all
three fields: source instance, namespace/board and native ID.

Task links now fail closed unless their exact (instance, namespace) pair is in
`SourceBinding.task_scopes`. Example, with a registered reducer role/feed:

    binding = SourceBinding(
        source='urn:synthetic:actor-a', runtime='instance-a',
        role='actor-a', feed='actor-a',
        task_scopes=(('task-service-a', 'board-a'), ('task-service-a', 'board-b')))

Empty `task_scopes=()` means no task links, not wildcard permission. CE source
must also exactly match binding.source. OTLP source/resource fields are
metadata, never authority to select another runtime or expand task permissions.
Task scope is checked by the same domain validator for CloudEvents, mapped
OTLP and durable snapshot pages, before state/index/cursor publication. The
allowlist is at most 256 unique, nonempty string pairs. Old persisted bindings
without the field reopen with the empty fail-closed default; existing retained
facts are preserved, but future task links require explicit local configuration.
The A07 task fixture now declares its existing task permission explicitly.

## Read-only SQLite primitive (not a live collector)

`workshop.acquisition.read_table` is a small local-code primitive intended for
a later approved schema adapter. It does not discover databases, import native
initialisers, contact sources on its own, map task rows to runtime executions,
or claim a supported Hermes schema. All Phase 1 acquisition files are synthetic
pytest fixtures. Phase 2 still owns one real approved workflow and schema mapping.

    result = read_table(
        synthetic_path, table='tasks',
        schema=(('id', 'TEXT'), ('board', 'TEXT'), ('disposition', 'TEXT')),
        where={'board': 'approved-board'}, limit=128)
    # result.rows: detached tuple of dictionaries; result.truncated: bool

Only trusted adapter configuration supplies path, table/schema and equality
filters. Never expose this function as arbitrary user SQL or a file browser.
The path is URI-escaped, connected with `mode=ro`, `query_only=ON` and
`trusted_schema=OFF`; no `immutable=1`, including for live WAL. It checks the
exact ordered names and declared types using table_xinfo inside the same short
read transaction as the SELECT. Extra columns, unknown tables/views/virtual
tables, unsupported schema, malformed identifiers, unapproved filter columns,
oversized values and invalid limits fail without returning partial rows.
Filter values are parameterised; no arbitrary SQL or connection escapes.

Bounds: 1–256 result rows, one lookahead to flag truncation, 64 KiB SQLite value/
row and encoded record limit, 1 MiB aggregate JSON result budget, 100,000 SQLite
VM instructions, 0.1-second lock timeout. Rows are consumed incrementally and
stop on the aggregate bound, not after fetching the whole batch. Unsupported
BLOB/non-finite/invalid-text values reject; this is not a generic binary export.
SQLite can raise OperationalError for busy/VM-budget/schema problems; reacquire
according to the adapter policy, never reinterpret failure as empty inventory.
The connection closes on every path; no transaction survives a call. The API
has no pagination cursor: a truncated result must not be represented as complete
coverage or a stable page boundary. An untruncated table result is still NOT
proof of complete runtime scope or an atomic source stream watermark. Do not
feed it into A08 complete-runtime recovery without a real adapter contract.

Read-only means native records/schema and database content are not changed.
It does not promise zero OS/filesystem side effects: SQLite may create/update
WAL shared-memory/coordination sidecars while reading a live WAL database. Never
use immutable mode to hide this. Fixture assertions verify rollback database
bytes/schema/records unchanged and live WAL database/WAL bytes unchanged; WAL
sidecar behaviour is not a zero-mutation or no-locking claim. The Workshop-owned
historian remains a separate file and is the only writable database surface.

## Fixed-off native-write interlock

LocalAPI exposes snapshot and authorised Workshop-local alarm acknowledgement
only. The controller position cannot enable native writes; the property has no
setter, executor or enable option. Durable ingress writes Workshop records,
not native sources. The SQLite primitive exposes only fixed SELECT/schema
reads. Structural tests pin the public callable surfaces and exact module
imports (including urllib.parse, not urllib.request), and reject native routes
at every UI position even with authorization. These are regression guards plus
source review, not a Python sandbox for malicious local code.

## Synthetic demo and development

See README for source-only install/test/demo/check commands. Demo seeds three
identical native IDs across distinct scoped task keys and runtime instances,
plus available-idle and configured/unobserved roles. It prints deterministic
JSON at a fixed acquisition clock. It creates no file, reads no real source,
starts no listener and does not establish operational acceptance.
