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

Run the approved migration command from the repository root:

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

## Copy-based verification

Before approving a live cutover, migrate a SQLite-consistent temporary copy:

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

Before a live migration:

- stop imports and other writes;
- record relevant table counts and dashboard totals;
- migrate and verify a copy;
- preserve the live pre-migration backup;
- run integrity, version, count, total and representative-decision checks after
  the approved migration.

Restoring a backup replaces financial state and requires separate explicit
approval. Follow [`OPERATIONS_AND_RECOVERY.md`](OPERATIONS_AND_RECOVERY.md).
