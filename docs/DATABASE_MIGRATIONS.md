# Database migrations

This document defines ClearSpend's maintained schema-versioning mechanisms.
Migration execution is an explicit administrative action; ordinary server
startup only verifies compatibility.

## Supported databases

PostgreSQL is authoritative. The retained SQLite database is an archival
pre-cutover snapshot and remains supported only for compatibility tests and
inspection.

Migration ownership is under `src/clearspend/database/`:

```text
database/
├── backup.py
├── connection.py
├── migration_runner.py
├── postgresql_backup.py
├── postgresql_migration_runner.py
├── postgresql_migrations/
├── postgresql_provisioning.py
├── schema.py
└── migrations/
```

One-time SQLite-to-PostgreSQL copy and parity tooling is not part of the
maintained application. PostgreSQL recovery uses encrypted PostgreSQL backups,
not the archival SQLite snapshot.

## PostgreSQL provisioning and migrations

Provisioning is a separate administrative operation. It creates and verifies:

- the private `clearspend` schema;
- the restricted `clearspend_app` login;
- administrative ownership of schema objects;
- explicit runtime grants;
- denial of schema access to Supabase API roles; and
- the restricted runtime search path.

The running application never receives the administrative `postgres`
credential. Provisioning is retained because a replacement or recovery
environment must be reproducible.

With the application server stopped, inspect, provision, and migrate through
the maintained command interface:

```bash
PYTHONPATH=src:. .venv/bin/python -m clearspend.admin status \
  --admin-config data/postgresql-admin.json
PYTHONPATH=src:. .venv/bin/python -m clearspend.admin provision \
  --admin-config data/postgresql-admin.json \
  --runtime-config data/postgresql-runtime.json
PYTHONPATH=src:. .venv/bin/python -m clearspend.admin migrate \
  --admin-config data/postgresql-admin.json
```

`status` is read-only. `provision` reads the admin and runtime-role passwords
from their separate Keychain items. `migrate` uses only the admin credential.
Success reports the schema state or exact version transition; configuration,
credential, connectivity, verification, and transactional migration failures
return a nonzero status without starting the application.

The PostgreSQL migration runner:

- accepts only an explicitly opened administrative pool;
- requires provisioning to have completed;
- rejects missing, non-contiguous, or newer versions;
- applies, verifies, and records each migration transactionally;
- grants the exact required privileges to `clearspend_app`; and
- never runs implicitly during normal startup.

Current migrations are ordered modules under
`database/postgresql_migrations/`:

1. Core imports, transactions, and observation reviews.
2. Transaction browsing, corrections, income, events, and event membership.
3. Merchant rules, import coverage, recurring profiles, membership, and the
   restricted merchant-category trigger.
4. Exact import-to-transaction linkage used by duplicate and batch-decision
   workflows.
5. Exact PostgreSQL `NUMERIC` storage for transaction amounts, exchange rates,
   reimbursements, income, event budgets, and statement totals.

The runner verifies required objects, ownership, grants, API-role denial, and
the expected migration history after application.

## Adding a PostgreSQL migration

1. Add the next contiguous migration module.
2. Keep it deterministic and transaction-safe.
3. Create every object with an explicit owner and grant only the permissions
   required by `clearspend_app`.
4. Preserve provider evidence, transactions, mappings, overrides,
   reimbursements, events, recurring decisions, reviews, coverage, and audit
   history unless the approved change explicitly requires otherwise.
5. Verify tables, columns, indexes, sequences, constraints, triggers,
   ownership, runtime grants, and API-role denial.
6. Test empty-schema application, a second inspection, deliberate failure,
   rollback, and representative preserved data.
7. Create and verify an authenticated encrypted PostgreSQL backup before
   applying an approved migration to authoritative data.
8. Run the migration with the server stopped, then restart and perform health
   and representative workflow checks.

Do not add opportunistic `ALTER TABLE` statements to startup and do not use
automatic privilege inheritance as a substitute for explicit grants.

## Backup and recovery boundary

`database.postgresql_backup` streams a schema-scoped custom-format `pg_dump`
through AES-256-CBC with PBKDF2 without creating a plaintext intermediate. It
publishes two mode-`0600` files:

- `*.dump.enc` — encrypted archive;
- `*.dump.enc.integrity` — versioned PBKDF2-derived HMAC-SHA-256 metadata.

Creation decrypts and lists the archive to verify all maintained tables before
publication. Restore requires the matching integrity file, verifies the HMAC
before decryption, refuses a target where the private schema already exists,
restores in one transaction, and verifies the table and migration inventory.
Both files are required for recovery and must be stored together; the archive
passphrase remains separate in macOS Keychain.

See [`OPERATIONS_AND_RECOVERY.md`](OPERATIONS_AND_RECOVERY.md) for the approved
backup, standalone verification, and combined replacement-environment restore
commands. The restore command bootstraps only the runtime role before restoring
the schema-bearing archive; ordinary provisioning must not run first because it
would make the target nonempty.

## SQLite compatibility migrations

The legacy SQLite runner remains for temporary synthetic tests and archival
inspection:

```bash
PYTHONPATH=src:. .venv/bin/python -m clearspend.server \
  --legacy-sqlite-database data/clearspend.db \
  --migrate-database
```

It inspects the schema, rejects unsupported shapes, creates a verified SQLite
backup when pending work exists, applies each migration transactionally, and
verifies the final state. It is not the PostgreSQL production migration path.

`tools/verify_migration_copy.py` verifies legacy SQLite migration behavior on a
temporary SQLite backup. It does not copy data to PostgreSQL.

## Test expectations

Tracked tests cover runner inspection, ordered application, statement
generation, permissions, rollback, backup orchestration, and runtime
compatibility. A separate CI job provisions a disposable PostgreSQL 17 service,
creates Supabase-style API roles, runs provisioning and all migrations, connects
through `clearspend_app`, exercises representative feature reads and writes,
proves approved-import commit and rollback, and checks access denial. It uses
only synthetic data and never connects to the private Supabase project.

Administrative command dispatch, backup orchestration, and recovery ordering
remain covered synthetically. Supabase TLS,
Session-pooler, and hosted-project configuration remain deployment checks.
