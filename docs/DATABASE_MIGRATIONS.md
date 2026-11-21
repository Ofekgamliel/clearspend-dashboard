# Database migrations

This document defines the current ClearSpend schema-versioning mechanism and
the requirements for future schema changes. A migration command is a separate,
explicit operation; reading this document does not authorize changing the live
database.

## Current implementation

Migration ownership is under `src/clearspend/database/`:

```text
database/
├── backup.py
├── connection.py
├── migration_runner.py
├── postgresql_backup.py
├── postgresql_copy.py
├── postgresql_migration_runner.py
├── postgresql_migrations/
├── schema.py
└── migrations/
    └── v001_current_baseline.py
```

`schema_migrations` records ordered versions, names, and application timestamps.
Version 1 represents the current baseline schema. Importing Python modules does
not migrate a database, and ordinary startup never upgrades a compatible
non-empty database implicitly.

Fresh or empty databases are initialized through the migration runner. Existing
compatible unversioned databases remain readable, but registration as version 1
is an explicit migration operation. An unknown, partial, or newer-than-supported
schema is rejected rather than guessed or rebuilt.

## Inspecting and migrating

The following command is the legacy SQLite migration command. It is retained
for compatibility testing and archival inspection; it is not the production
PostgreSQL migration path:

```bash
PYTHONPATH=src:. .venv/bin/python -m clearspend.server --migrate-database
```

The command:

1. Inspects the current schema.
2. Rejects unsupported shapes before changing them.
3. Creates and verifies a timestamped SQLite backup when a non-empty database
   has pending work.
4. Applies each migration and its version record transactionally.
5. Runs migration and final-schema verification.
6. Exits without starting the web server.

If no migration is pending, it performs no backup and no schema write.

The status of a particular private database must be established by inspection;
tracked documentation must not assume whether that local database is versioned.

## SQLite copy-based verification

The completed PostgreSQL cutover used this utility to migrate and verify an
SQLite-consistent temporary copy:

```bash
PYTHONPATH=src:. .venv/bin/python tools/verify_migration_copy.py data/clearspend.db
```

The utility opens the source read-only, creates the temporary copy with SQLite's
backup API, migrates only that copy, and compares existing tables plus
representative API payloads. It prints generic status and counts rather than
private records.

## Schema states

`inspect_database(path)` reports one of these states:

- `empty` — no initialized application schema.
- `current_unversioned` — schema matches the supported baseline but has no
  migration record.
- `versioned` — supported migration metadata and schema are present.
- `unsupported` — required objects are missing, inconsistent, or newer than the
  running application understands.

An unsupported state is a stop condition. Do not add opportunistic `ALTER
TABLE`, silent backfills, or automatic database replacement to server startup.

## Migration representation

Each migration is a small ordered Python module under
`database/migrations/` with fixed metadata and explicit apply/verify functions:

```python
VERSION = 2
NAME = "descriptive_change"

def apply(connection): ...
def verify(connection): ...
```

Versions are unique, contiguous positive integers. A version record is written
only after application and verification succeed. Migration modules may use
database helpers but must not import HTTP or frontend code.

Use Python migration modules rather than raw SQL files when a safe change needs
data validation, a deterministic backfill, or post-change verification.

## Adding a future migration

1. Describe the stored-data change and compatibility impact.
2. Add the next contiguous migration module.
3. Keep the migration deterministic and safe to retry after rollback.
4. Preserve transactions, provider evidence, mappings, overrides,
   reimbursements, events, recurring decisions, reviews, coverage and audit
   records unless the approved change explicitly says otherwise.
5. Add synthetic tests for the old supported shape, successful upgrade,
   idempotent second run, verification failure and rollback.
6. Verify a private database copy before considering the live database.
7. Update the schema inventory and affected API contracts only when their
   maintained semantics change.

Do not create an empty placeholder migration or example production version.

## Required test coverage

Migration coverage must include:

1. Empty database creation at the current version.
2. Compatible unversioned baseline registration without row changes.
3. No-op behavior when run a second time.
4. Rejection of unknown or partial schemas without modification.
5. Verified backup before pending work on a non-empty database.
6. Rollback of schema, data, and version state after deliberate failure.
7. Verification of required tables, columns, indexes and triggers.
8. Preservation of representative financial and reviewed records.

Tests use temporary synthetic databases. See [`TESTING.md`](TESTING.md).

## Backup, failure, and recovery

A pending migration for a non-empty database requires a backup directory.
Backups use SQLite's backup API and integrity verification; they are not raw
copies of a potentially active database with unresolved WAL state.

Each migration applies inside a transaction where SQLite permits. A failure
rolls back that migration and leaves the verified pre-migration backup in place.
The runner reports the backup path but never restores or deletes files
automatically.

Before a legacy SQLite migration:

- stop imports and other writes;
- record relevant table counts and dashboard totals;
- migrate and verify a copy;
- preserve the live pre-migration backup;
- run integrity, version, count, total and representative-decision checks after
  the approved migration.

Restoring a backup replaces financial state and requires separate explicit
approval. Follow [`OPERATIONS_AND_RECOVERY.md`](OPERATIONS_AND_RECOVERY.md).

## PostgreSQL migration development

PostgreSQL uses a separate runner because SQLite backup and inspection
mechanics do not apply to a hosted database. The PostgreSQL runner:

- accepts only an explicitly opened administrative pool;
- requires the private `clearspend` schema to have been provisioned first;
- rejects missing, non-contiguous, or newer migration versions;
- applies, verifies, and records each migration in one transaction; and
- never provisions credentials, silently falls back to SQLite, or runs during
  ordinary server startup.

Before the first migration, the explicit PostgreSQL provisioning operation
creates and verifies the `clearspend_app` role and `clearspend` schema. It is
separate from migration history because credentials and database objects have
different rotation and recovery lifecycles. Migration execution refuses an
unprovisioned schema.

PostgreSQL migration 1 defines the first dependency-complete feature slice:
`imports`, `transactions`, and `observation_reviews`, with their identity
sequences, indexes, explicit `clearspend_app` grants, API-role denials, and
ownership verification. It intentionally preserves amount, date, payload, and
identifier representations as text for initial behavioral parity.

The migration has synthetic runner, statement, catalog, grant, and failure
tests. It has also been applied transactionally to the empty hosted private
schema through the approved Session-pooler exception. Hosted verification
confirmed the restricted runtime role could insert synthetic dependencies,
save/read/undo an observation review through the real feature services, and
remove every smoke-test row. No private financial data was copied.

PostgreSQL migration 2 adds the transaction-browsing dependency set:
transaction category overrides, reimbursement adjustments, merchant display
identities, income coverage, events, and exact event membership. The extra
tables are structural dependencies for the transaction read model; their
feature services remain owned and ported by their later migration slices.

Migration 2 was applied and verified transactionally through the Session
pooler. A hosted synthetic smoke check confirmed case-insensitive transaction
search, category override persistence, reimbursement persistence, and the
portable personal-spending calculation through `clearspend_app`. Cleanup checks
confirmed that no smoke-test imports, transactions, corrections, or orphaned
rows remained. No private financial data was copied.

PostgreSQL migration 3 adds permanent merchant category rules, import coverage,
reviewed recurring profiles and exact recurring membership. Coverage and
recurring tables are dependencies of the merchant read model; their owning
write workflows remain later portability slices. The migration also installs a
restricted, fixed-search-path trigger function that applies an exact merchant
category rule before a new transaction is inserted. The function preserves an
incoming category when no exact rule exists, cannot be called by the runtime or
Supabase API roles, and is exercised indirectly by transaction insertion.

Migration 3 was applied and verified transactionally through the Session
pooler. A hosted synthetic smoke check through `clearspend_app` confirmed
historical recategorization, future exact-name rule application, display
identity/category independence, merchant read assembly, and statement coverage
context. Cleanup checks confirmed zero synthetic imports, transactions, and
coverage rows remained. No private financial data was copied.

The event feature slice requires no additional schema migration because
migration 2 created `events`, `event_transactions`, their foreign keys, index,
and explicit grants as transaction-read dependencies. Its feature query and
service modules now use the shared connection and transaction boundaries. A
hosted synthetic check through `clearspend_app` verified event creation,
assignment, month-scoped reads, settings edits, preservation of exact membership
across date changes, and unassignment. Cleanup confirmed zero synthetic event,
membership, transaction, and import rows remained.

The recurring feature slice also requires no additional schema migration:
migration 3 created reviewed profiles and exact alias membership as merchant
read dependencies. Shared recurring SQL uses database-neutral boolean values
and numeric casts, and its services own complete profile/membership
transactions through the shared boundary. A hosted synthetic check through
`clearspend_app` verified selected-alias history, month-scoped recurring totals,
lifecycle editing, and preservation of reviewed membership when a profile is
marked not recurring. Cleanup confirmed zero synthetic profiles, memberships,
transactions, and imports remained.

The category and shared-reporting-scope slice requires no schema migration.
Category aggregation now uses the shared database connection boundary, named
scalar results, portable personal-spending expressions, and numeric rounding
accepted by both engines. The pure period/card/event-scope builder remains the
single owner of those predicates. A hosted synthetic check through
`clearspend_app` verified totals, previous-month comparison, new-category
detection, card filtering, and routine-only exclusion of exact event members.
Cleanup confirmed zero synthetic events, memberships, transactions, and imports
remained.

The dashboard reporting and income slice requires no schema migration because
migration 2 created the income tables and their identity sequences as dashboard
dependencies. The dashboard read model now uses the shared connection boundary,
portable numeric casts and rounding, named scalar fields, and explicit float
normalization before JSON serialization. Computed reporting-month aliases avoid
PostgreSQL date keywords while preserving the response contract. A hosted
synthetic check through `clearspend_app` verified spending, refunds in billing
trends, household income, remaining balance, card totals, available months, and
month/year trend assembly. Cleanup confirmed zero synthetic financial and
income rows remained.

The observation-input and installment-read slice requires no schema migration.
Its composed loader now accepts the shared database target used by dashboard,
transaction, recurring, and review reads. The dedicated historical-installment
query uses portable numeric casts while retaining stable plan identity and
month-indexed empty coverage. A hosted synthetic check through
`clearspend_app` verified history scope, transaction inputs, household income
visibility, installment totals and identities, and active review keys. Cleanup
confirmed zero synthetic financial, income, and review rows remained.

PostgreSQL migration 4 adds `import_transactions`, the exact import-to-
transaction linkage used for duplicate evidence and newly inserted batch
decisions. It preserves the established integer duplicate flag, composite key,
foreign keys, explicit runtime grants, API-role denial, and administrative
ownership. Hosted verification through `clearspend_app` confirmed linkage
writes and reads together with portable staged reference, nullable duplicate,
and coverage analysis. Cleanup confirmed zero synthetic imports, transactions,
linkages, and coverage rows remained.

Approved PostgreSQL imports are now the production path. The import repository
supports caller-owned PostgreSQL transactions, portable returned identities
and conflict handling, and automatic PostgreSQL metadata minimization. A real
disposable rehearsal through `clearspend_app` verified statement and income
inserts plus duplicate linkage. The complete reviewed-write sequence now also
runs inside a caller-owned PostgreSQL transaction, including merchant
decisions, exclusions, overrides, coverage, audit counts, duplicate linkage,
commit, and rollback. The PostgreSQL commit boundary acquires an advisory
transaction lock, creates and verifies the encrypted backup with
`clearspend_app`, and only then writes. Production server routing is active
through the restricted runtime configuration. Off-device storage, retention,
and key-recovery gates are complete. Preview remains read-only independently of
the commit boundary.

The first connection-level recovery rehearsal has completed against the empty
hosted schema. A PostgreSQL 19 `pg_dump` custom archive created through the
session pooler restored successfully into an isolated PostgreSQL 17 database.
Verification recovered all 16 tables and migration versions 1 through 4,
preserved administrative ownership and explicit runtime grants, denied schema
creation and direct execution of the trigger function to `clearspend_app`, and
confirmed zero financial rows. The temporary archive and restore target were
removed. This established the hosted connection and archive format; the later
complete synthetic rehearsal described below establishes the
application-owned encrypted recovery path.

The encrypted archive creator is now implemented in
`database.postgresql_backup`. It streams a schema-scoped custom-format dump
through AES-256-CBC with PBKDF2 rather than writing a plaintext intermediate
archive. Database and encryption passwords come from separate Keychain items,
must differ, and are provided only through isolated child-process environments.
The final archive is mode `0600`; it is published only after a decrypt-and-list
verification proves that all current ClearSpend tables are present. Any failed
command, invalid listing, or missing table removes the partial artifact. The
paired restore orchestration refuses an occupied target, decrypts directly into
a single-transaction `pg_restore`, and verifies all 16 tables and four migration
rows afterward. A real-tool rehearsal then copied the complete linked 15-table
fixture into PostgreSQL, created a mode-`0600` encrypted archive through this
component, restored it into a separate empty TLS PostgreSQL target, and proved
exact source/target hashes, migrations, sequences, minimization, and
permissions. A second restore was refused because the target was occupied. All
temporary rehearsal artifacts were removed. The component is integrated into
the production pre-import write boundary, and its off-device storage,
retention, and recoverable-key requirements are active.

The production implementation has also completed a real-tool empty-schema
exercise. It created an encrypted archive through the hosted session pooler,
verified it, stream-decrypted it directly into an isolated PostgreSQL 17
database, and recovered all 16 tables, migration versions 1 through 4,
administrative ownership, and restricted runtime privileges. No plaintext dump
was written and the temporary archive and restore cluster were removed. The
later complete synthetic recovery rehearsal closed the data-bearing restore
exercise. The off-device key and retention decisions are complete.

The deterministic copy foundation is implemented in
`database.postgresql_copy`. It reads SQLite through a query-only connection,
checks the maintained schema plus SQLite integrity and foreign-key reports,
requires exact PostgreSQL migration history 1 through 4 and zero destination
data, and inserts every data table in dependency order within one destination
transaction. Each table is read back in primary-key order and compared by count
and a deterministic SHA-256 content hash before commit. Explicit IDs are
preserved and all four identity sequences are advanced. Any mismatch or later
table failure rolls back the whole destination copy.

The caller must provide the data-minimization policy explicitly. The approved
PostgreSQL policy preserves statement filenames, replaces full `source_path`
values with those filenames, removes stored error messages, removes raw
transaction payloads, and carries no staging-only metadata. Contradictory
choices are rejected. A disposable real-PostgreSQL rehearsal has copied one
linked synthetic row through every one of the 15 application data tables. It
verified minimization, relationships, identities, all four sequences, counts,
hashes, runtime readability, and API-role denial, then removed the temporary
SQLite source, PostgreSQL database, and server cluster.
