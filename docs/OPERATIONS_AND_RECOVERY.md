# Operations, backups, and recovery

This document covers local startup, database backups, import recovery, and safe
movement of ClearSpend's private state. Run commands from the repository root.

## Start and stop

Start the application:

```bash
PYTHONPATH=src:. .venv/bin/python -m clearspend.server --port 8765
```

Open `http://localhost:8765`. Verify the API at
`http://localhost:8765/api/health` when troubleshooting.

If the port is already occupied, identify the process before stopping it:

```bash
lsof -nP -iTCP:8765 -sTCP:LISTEN
```

Stop the known ClearSpend process normally with `Ctrl-C`, or use `kill <pid>`
after verifying its command. Do not terminate an unknown process merely to free
the port.

## Database locations

- Live database: `data/clearspend.db`
- Automatic and manual backups: `data/backups/`
- Local mapping exports and research: other ignored paths under `data/`

All are private and excluded from Git. Backup files are not automatically
uploaded or pruned.

## Automatic import backup

Staging a statement is read-only. Immediately before an approved staged import
is committed, ClearSpend copies the live database to:

```text
data/backups/clearspend-before-import-YYYYMMDD-HHMMSS-microseconds.db
```

The backup protects the pre-import state. Keep the import filename, audit record,
coverage record, and post-import verification together when diagnosing a batch.

## Manual backup

Before a migration, bulk correction, duplicate repair, or other material edit,
stop the server and create a timestamped copy:

```bash
mkdir -p data/backups
cp -p data/clearspend.db data/backups/clearspend-manual-YYYYMMDD-HHMMSS.db
```

Replace the timestamp placeholder with the actual date and time. Verify that the
backup exists and can be opened before continuing. If taking a backup while the
application is live, use SQLite's backup facility instead of copying a database
with possible active sidecar files.

## Restore a backup

Restoring replaces the current financial state and therefore requires explicit
user approval.

1. Stop the ClearSpend server.
2. Preserve the current database as a separate timestamped rollback copy.
3. Confirm the exact backup path and its creation time.
4. Copy the approved backup to `data/clearspend.db`.
5. Restart ClearSpend and check `/api/health`.
6. Verify import counts, transaction totals, income, mappings, events, recurring
   decisions, and representative periods before deleting nothing.

Do not use `git reset`, a fresh clone, or source-file recovery to restore the
database. Git intentionally has no copy of the financial state.

## Import verification and rollback

After every committed import, compare the staged preview with the audit result:

- provider, statement filename, import timestamp, cards, and coverage dates;
- inserted, exact-duplicate, possible-duplicate, pending, and outside-cycle
  counts;
- parsed totals versus official totals across every relevant sheet or tab;
- unresolved merchant decisions and representative inserted rows;
- dashboard totals and the last transaction date for each affected card.

If the result is wrong, stop further imports. Prefer a targeted, audited repair
when the inserted rows are correct but a mapping or category is wrong. Restore
the pre-import backup only when the batch itself must be rolled back, and only
after preserving the current database for comparison.

## Moving ClearSpend to another computer

Clone the repository for the application code, create its virtual environment,
and transfer `data/clearspend.db` separately through an approved encrypted or
direct local method. Do not commit the database, statements, or backups to the
repository. Start the application and perform the same health and representative
data checks used after a restore.
