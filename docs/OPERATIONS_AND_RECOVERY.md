# Operations, backups, and recovery

This document covers local startup, database backups, import recovery, and safe
movement of ClearSpend's private state. Run commands from the repository root.

## Start and stop

PostgreSQL is the authoritative database. Start the local application from the
repository root with the ignored Frankfurt runtime configuration:

```bash
PYTHONPATH=src:. .venv/bin/python -m clearspend.server \
  --postgresql-config data/postgresql-frankfurt-runtime.json \
  --port 8765
```

Keep that terminal process running while using ClearSpend. Stop the known
process normally with `Ctrl-C`.

The server still supports a legacy SQLite mode for development and recovery
inspection, but omitting `--postgresql-config` selects that mode. The retained
SQLite file is an archival pre-cutover snapshot and must not be used for normal
reads, edits, or imports. There is no automatic fallback between PostgreSQL and
SQLite: if PostgreSQL is unavailable, ClearSpend must remain unavailable until
the PostgreSQL service is restored.

The PostgreSQL configuration contains endpoint metadata, explicit CA and tool
paths, local state and backup directories, and Keychain item names. It must not
contain either database password or the archive passphrase. The server refuses
to bind until it can open the restricted pool and verify the current schema.
Download the project certificate from Supabase **Database Settings → SSL
Configuration → Download Certificate** and keep it under the ignored
`data/certificates/` directory. Do not substitute the macOS system CA bundle:
the project pooler requires the Supabase certificate for `verify-full`.

Open `http://localhost:8765`. Verify the API at
`http://localhost:8765/api/health` when troubleshooting.

The running Python process does not change when Git branches change. Stop and
restart ClearSpend after switching between `main` and another branch so the
served frontend and backend API come from the same checkout. A compatible
health response contains `status: ok`, `database: true`, and the API
compatibility identifier expected by the frontend. If they do not match, the
dashboard intentionally withholds its data panels and offers a retry action.

Before browser acceptance testing, check health explicitly:

```bash
curl -fsS http://127.0.0.1:8765/api/health
```

Do not continue browser acceptance testing if this request fails, reports a
missing database, or returns a different compatibility identifier.

If the port is already occupied, identify the process before stopping it:

```bash
lsof -nP -iTCP:8765 -sTCP:LISTEN
```

Stop the known ClearSpend process normally with `Ctrl-C`, or use `kill <pid>`
after verifying its command. Do not terminate an unknown process merely to free
the port.

## Database locations

- Authoritative database: private Supabase PostgreSQL `clearspend` schema
- Active ignored runtime configuration:
  `data/postgresql-frankfurt-runtime.json`
- Archival pre-cutover SQLite snapshot: `data/clearspend.db`
- Verified SQLite archival backups: `data/backups/`
- Encrypted PostgreSQL backups: `data/backups/postgresql/`
- Local mapping exports and research: other ignored paths under `data/`

All are private and excluded from Git. Backup files are not automatically
uploaded or pruned.

The PostgreSQL backup directory is local-only and mode `0700`. Until
automatic off-device storage is selected, manually upload each verified
`.dump.enc` file to a private Google Drive folder. Confirm that the uploaded
filename and file size match the local file before treating the off-device copy
as present. Never upload the archive passphrase, Keychain export, raw dump,
SQLite database, or statement files beside it. Keep every local encrypted
archive and its private Google Drive copy for now; no automatic retention or
deletion is enabled. Replacing this keep-all policy requires a later explicit
decision.

## PostgreSQL production status

The controlled cutover completed on 2026-11-21. PostgreSQL is the sole
authoritative reader and writer. The local Vue application and Python server
remain available only on this computer; moving the database to Supabase did not
make the dashboard public. The Supabase Data API is disabled because ClearSpend
uses only the restricted PostgreSQL connection through the Session pooler.

The ignored configuration, project-specific Supabase CA certificate, and
macOS Keychain references are required for startup. Never paste either the
`postgres` or `clearspend_app` password into a tracked file, command-line
argument, log, or documentation.

Provisioning is a separate administrative operation. It requires the Supabase
`postgres` connection, creates the restricted `clearspend_app` login and
private `clearspend` schema, and verifies role attributes, ownership, schema
privileges, memberships, API-role denial, and the restricted search path. The
runtime password is converted locally to a SCRAM-SHA-256 verifier before SQL is
built, so plaintext is not embedded in the statement. If the role already
exists, provisioning verifies it but does not silently replace its password.
Credential rotation is a separate explicit operation.

The provisioning function is not wired to server startup or a general command.
Provisioning and all four schema migrations have been run and verified. Keep
the runtime password in a separate Keychain item from the administrative
password; the running application must never receive the `postgres` credential.

The direct database endpoint requires IPv6, which is unavailable on the current
local network. The approved runtime therefore uses the shared Session pooler.
Client connections enforce TLS `verify-full`; the restricted runtime role owns
no application objects and receives only the explicit grants required by the
four migrations.

The application-owned backup component streams `pg_dump` through encryption,
uses separate database and archive credentials, assigns each archive mode
`0600`, and decrypts it in memory for structural verification before publishing
it. The recovery path restores only into an empty approved PostgreSQL target and
verifies tables and migration history afterward. Keep every local and private
off-device encrypted archive until the retention policy is explicitly changed.

The approved production copy preserved all 15 application data tables and
passed the complete cross-engine calculation and presentation comparison before
authority changed. The parity verifier remains available for investigation:

```bash
PYTHONPATH=src:. .venv/bin/python tools/verify_postgresql_parity.py \
  data/clearspend.db \
  --postgresql-config data/postgresql-frankfurt-runtime.json
```

It compares dashboard calculations, recent transaction presentation, complete
transaction rows and ordering, every monthly dashboard, representative card
scopes, scoped search/filter results, and representative financial observations.
Output contains only a comparison count, a combined hash, and the
source-unchanged result; it never prints financial payload values.

The initial pool acquisition/connect timeout is 15 seconds. The original
5-second value proved too short during an empty-schema Session-pooler smoke
check and failed before SQL execution. A timeout remains a clear unavailable
error and never triggers SQLite fallback.

## Automatic import backup

Staging a statement is read-only. In the legacy SQLite mode, immediately before
an approved staged import is committed, ClearSpend acquires a SQLite write
reservation, creates a consistent backup with SQLite's backup API, and verifies
the source and backup with `PRAGMA integrity_check`:

```text
data/backups/clearspend-before-import-YYYYMMDD-HHMMSS-microseconds.db
```

The backup protects the pre-import state. The reviewed statement is then saved
as one transaction: merchant decisions, transactions, duplicate links, coverage
and audit rows either all commit or all roll back. Keep the import filename,
audit record, coverage record and post-import verification together when
diagnosing an import.

The authoritative PostgreSQL path supports staged preview and a complete
reviewed commit boundary. It serializes imports with an advisory transaction lock,
creates and verifies the encrypted backup using `clearspend_app`, then writes
merchant decisions, transactions, duplicate links, exclusions, overrides,
coverage, and audit rows in one transaction. Upload each new verified encrypted
archive to the approved private off-device location.

If commit validation or persistence fails, no partial approved import is kept.
The staged session remains available for a corrected retry while the same server
process is running. Cancelling it removes the temporary upload; restarting the
server also means the original statement must be staged again.

## Archival SQLite backup

The following procedure applies only to preserving the archival SQLite snapshot;
it is not a backup of the live PostgreSQL database. With the server stopped,
create a timestamped copy when another archival copy is required:

```bash
mkdir -p data/backups
cp -p data/clearspend.db data/backups/clearspend-manual-YYYYMMDD-HHMMSS.db
```

Replace the timestamp placeholder with the actual date and time. Verify that the
backup exists and can be opened before continuing. If an SQLite database is
active during compatibility testing, use SQLite's backup facility instead of
copying a database with possible active sidecar files.

PostgreSQL imports create encrypted backups automatically. PostgreSQL schema
migrations, bulk repairs, and recovery have their own verified-backup workflow.
Follow
[`DATABASE_MIGRATIONS.md`](DATABASE_MIGRATIONS.md) rather than manually editing
schema objects.

## Restore authoritative PostgreSQL

Restoring replaces the current financial state and therefore requires explicit
user approval.

1. Stop the ClearSpend server.
2. Preserve and verify the current PostgreSQL state when it is still reachable.
3. Confirm the exact encrypted archive and its separately stored recovery key.
4. Restore only into an approved empty PostgreSQL target using the reviewed
   PostgreSQL recovery tooling.
5. Verify schema migrations, permissions, counts, relationships, hashes, and
   representative financial/API results before changing runtime configuration.
6. Restart ClearSpend with the approved PostgreSQL configuration and check
   `/api/health`.

Do not restore the archival SQLite snapshot over PostgreSQL activity and do not
copy PostgreSQL activity back into SQLite. After cutover, PostgreSQL recovery
uses PostgreSQL backups. Do not use `git reset`, a fresh clone, or source-file
recovery to restore financial data; Git intentionally has no copy of it.

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

Clone the repository for the application code and create its virtual
environment. Transfer the ignored PostgreSQL runtime configuration and Supabase
CA certificate through an approved private method, then create the required
Keychain items on the new computer. Do not commit configuration, credentials,
statements, SQLite snapshots, or backups to the repository. Start with
`--postgresql-config`, then perform the same health and representative data
checks used after a restore.
