# Database migration design

This document defines ClearSpend's migration mechanism. It does not authorize
a live database migration by itself.

## Implementation status

The version-1 schema definition and migration runner live under
`src/clearspend/database/` with synthetic coverage. Fresh databases are created
through that runner. Ordinary server startup validates an existing database
but does not register or migrate a compatible unversioned database. The live
database therefore remains unversioned until an explicit cutover is approved.

Run an approved migration as a separate operation:

```bash
PYTHONPATH=src:. .venv/bin/python -m clearspend.server --migrate-database
```

For a non-empty database, this command creates and verifies a timestamped
SQLite backup under `data/backups/` before applying pending migrations. It exits
without starting the server. Running the regular server command never performs
that cutover implicitly.

Copy-based verification is performed with:

```bash
PYTHONPATH=src:. .venv/bin/python tools/verify_migration_copy.py data/clearspend.db
```

The utility opens the source read-only, uses SQLite's backup API for the
temporary copy, migrates only that copy, and compares every existing table plus
representative API payloads before and after. It prints only generic counts and
status information.

## Goals

- Give every database an explicit schema version.
- Make fresh database creation and existing database upgrades deterministic.
- Stop performing hidden schema/backfill work in `ImportDatabase.__init__`.
- Back up a non-empty database before applying pending migrations.
- Fail safely when the existing schema is unknown or inconsistent.
- Preserve all transactions, mappings, overrides, adjustments, events,
  recurring profiles, reviews and import audit evidence.

## Migration metadata

Use a dedicated table rather than relying only on `PRAGMA user_version`:

```sql
CREATE TABLE schema_migrations (
  version INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  applied_at TEXT NOT NULL
);
```

Migration versions are ordered positive integers. A version is inserted only
after its migration and verification succeed.

## Initial baseline strategy

ClearSpend already has unversioned databases, so the first migration cannot
blindly recreate or alter the schema.

### Empty database

1. Create `schema_migrations`.
2. Apply the complete current baseline schema as version 1.
3. Verify required tables, columns, indexes and triggers.
4. Record version 1.

### Existing unversioned database

1. Open read-only for inspection first.
2. Compare its tables, columns, indexes and triggers with the expected current
   baseline fingerprint.
3. If it matches, create `schema_migrations` and record version 1 without
   rewriting user records.
4. If it does not match, stop with an explicit unsupported-schema report. Do
   not guess, rebuild or silently run old inline upgrades.

Supporting older shapes can be added later as explicit, tested compatibility
migrations when an actual older schema fixture is available.

## Runner behavior

The runner exposes explicit operations:

```text
inspect_database(path) -> schema status
pending_migrations(path) -> ordered migrations
migrate_database(path, backup_directory) -> applied versions and backup path
```

Rules:

1. Importing a Python module must never migrate the database.
2. Opening a repository must not perform opportunistic `ALTER TABLE` work.
3. If no migration is pending, startup performs no backup and no write.
4. If a migration is pending for a non-empty database, create and verify an
   SQLite-consistent backup first.
5. Acquire an appropriate SQLite write lock and apply one ordered migration at
   a time.
6. Apply transactional DDL/data changes and the version record in the same
   transaction where SQLite permits.
7. Run migration-specific verification before commit.
8. Roll back and report the preserved backup on failure.
9. Never delete old backups automatically.

## Migration representation

Use small Python migration modules because some ClearSpend changes require
data verification or backfills in addition to SQL. Each migration should
provide fixed metadata and two functions:

```python
VERSION = 2
NAME = "example_change"

def apply(connection): ...
def verify(connection): ...
```

Migration modules must not import HTTP or frontend code. They may use shared
database helpers that do not contain financial policy.

## Proposed package

```text
src/clearspend/database/
|-- __init__.py
|-- connection.py
|-- migration_runner.py
`-- migrations/
    |-- __init__.py
    |-- v001_current_baseline.py
    `-- v002_example_future_change.py
```

The first implementation should add only the runner, the current baseline and
tests. No example future migration should remain in production code.

## Required synthetic tests

1. An empty database is created at the current version.
2. A current unversioned database is registered without changing row data.
3. Running the runner twice is a no-op the second time.
4. An unknown or partial schema is rejected without modification.
5. A pending migration creates a verified backup before writing.
6. A deliberately failing migration rolls back schema, data and version state.
7. Required tables, columns, indexes and triggers exist after migration.
8. Representative transaction, mapping, event, recurring and income rows are
   unchanged when registering the baseline.

Tests must use temporary synthetic databases only.

## Cutover from current initialization

Implementation should happen in reversible steps:

1. Extract the current schema definition without changing behavior.
2. Add schema-fingerprint and migration-runner tests.
3. Register version 1 on synthetic copies of the current schema.
4. Test against a copy of the private live database and compare counts/totals.
5. Make fresh-database creation use the runner and make ordinary startup
   validate existing schemas without migrating them.
6. Remove inline `ALTER TABLE`, backfill and re-key work from
   `ImportDatabase.__init__` after parity is proven.
7. Run the full local regression suite and representative dashboard checks.

The real database must never be the first database used for this cutover.

## Backup and restore requirements

Before the first live migration:

- Stop new imports and other writes.
- Create an SQLite-consistent timestamped backup.
- Run `PRAGMA integrity_check` on both live and backup copies.
- Record relevant table counts and dashboard totals.
- Apply the migration.
- Verify the version, integrity, counts, totals and representative reviewed
  decisions.

Restoring a backup remains a separate destructive action requiring explicit
approval. The runner must report the backup path but must never restore or
delete files automatically.
