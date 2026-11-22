# Operations, backups, and recovery

This document covers normal startup, PostgreSQL backups, import recovery, and
safe movement of ClearSpend's private state. Run commands from the repository
root.

## Start and stop

Start the local application with the ignored PostgreSQL runtime configuration:

```bash
PYTHONPATH=src:. .venv/bin/python -m clearspend.server \
  --postgresql-config data/postgresql-runtime.json \
  --port 8765
```

Keep that process running while using ClearSpend and stop it normally with
`Ctrl-C`. Restart it after switching Git branches so the server and generated
frontend come from the same checkout.

Open `http://localhost:8765` and check
`http://localhost:8765/api/health` when troubleshooting. A compatible response
reports `status: ok`, `database: true`, and the API compatibility identifier
expected by the frontend.

The retained SQLite file is an archival pre-PostgreSQL snapshot. Starting
without a database selection fails. Archival inspection requires the explicit
`--legacy-sqlite-database data/clearspend.db` option, which must not be used for
normal reads, edits, or imports. PostgreSQL failure never triggers an automatic
SQLite fallback.

If port 8765 is occupied, inspect it before stopping anything:

```bash
lsof -nP -iTCP:8765 -sTCP:LISTEN
```

Do not terminate an unknown process.

## Runtime configuration and secrets

Start new ignored configuration files from the tracked synthetic templates:

```bash
mkdir -p data/certificates data/backups/postgresql
cp config/postgresql-runtime.example.json data/postgresql-runtime.json
cp config/postgresql-admin.example.json data/postgresql-admin.json
chmod 600 data/postgresql-runtime.json data/postgresql-admin.json
chmod 700 data data/backups data/backups/postgresql
```

Replace every `example-*` value with private endpoint metadata. Never put a
password in either JSON file. Relative paths are resolved from the directory
containing that configuration file, not from the shell's working directory.

The runtime file contains these required fields:

| Field | Meaning |
| --- | --- |
| `backend` | Must be `postgresql` |
| `expected_region` | Required Supabase region guard. The tracked templates use `eu-central-1`; startup fails if the pooler hostname names another region. |
| `host`, `port`, `database`, `user` | Supabase Session-pooler endpoint, normally port 5432, database `postgres`, and the project-qualified `clearspend_app` user |
| `ssl_root_certificate` | CA certificate used by TLS `verify-full` |
| `keychain_service`, `keychain_account` | Runtime database password lookup |
| `local_state_directory` | Private staging state for local uploads |
| `backup_directory` | Destination for encrypted backup pairs |
| `backup_encryption_keychain_service`, `backup_encryption_keychain_account` | Separate archive-passphrase lookup |

Optional runtime fields are `pool_min_size`, `pool_max_size`,
`acquisition_timeout_seconds`, `statement_timeout_milliseconds`,
`pg_dump_path`, `psql_path`, `pg_restore_path`, and `openssl_path`. The tracked
template supplies safe defaults for every optional field.

The admin file contains the same `backend`, `expected_region`, endpoint, CA, database Keychain,
pool, and timeout fields, but its project-qualified user and Keychain item refer
to the Supabase `postgres` administrator. It deliberately contains no local
state or archive settings.

Keep the Supabase CA certificate under ignored `data/certificates/` and use TLS
`verify-full`. Both configuration loaders require a region-qualified Session-
pooler hostname and reject a hostname whose region differs from
`expected_region`. The server prints the verified region after opening the
restricted pool and verifying the current schema. The running application uses
only the `clearspend_app` credential; provisioning and recovery use a separate
administrative credential.

The configuration files should be mode `0600`; private state and backup
directories should be mode `0700`. A CA certificate is public trust material
and may be mode `0644`, but it must come from the approved provider source and
must not be replaced without review.

Create or replace the three Keychain items interactively so secrets do not
appear in JSON, command arguments, or shell history:

```bash
security add-generic-password -a clearspend_app -s clearspend-example-runtime -U -w
security add-generic-password -a postgres -s clearspend-example-admin -U -w
security add-generic-password -a archive -s clearspend-example-backup -U -w
```

Use the exact service and account names selected in the two ignored files. The
runtime database password, admin database password, and archive passphrase must
be distinct.

macOS Keychain is the currently supported secret store. A generalized provider
is deferred while ClearSpend remains a local macOS application.

Validate restricted connectivity and schema compatibility without changing
financial state:

```bash
PYTHONPATH=src:. .venv/bin/python -m clearspend.admin runtime-status \
  --runtime-config data/postgresql-runtime.json
```

Success reports `versioned`, the current schema version, and `no problems`.
Missing files, Keychain entries, TLS trust, connectivity, or schema access fail
with a concise `ClearSpend admin error` and a nonzero exit status.

## Administrative command boundary

`clearspend.admin` is the maintained interface for PostgreSQL status,
provisioning, migrations, standalone backups, backup verification, and restore.
Run every command from the repository root. Stop the application server before
`provision`, `migrate`, or `restore`; those operations are never performed by
ordinary server startup.

Inspect the administrative connection without mutation:

```bash
PYTHONPATH=src:. .venv/bin/python -m clearspend.admin status \
  --admin-config data/postgresql-admin.json
```

Provision a new empty project, then apply all migrations:

```bash
PYTHONPATH=src:. .venv/bin/python -m clearspend.admin provision \
  --admin-config data/postgresql-admin.json \
  --runtime-config data/postgresql-runtime.json
PYTHONPATH=src:. .venv/bin/python -m clearspend.admin migrate \
  --admin-config data/postgresql-admin.json
```

Provisioning uses the admin credential and reads the runtime role password from
its separate Keychain item. It creates or verifies the restricted role and
private schema. Migration uses only the admin credential, applies each pending
version transactionally, and prints the starting, ending, and applied versions.
Both operations fail closed and leave a failed transaction uncommitted.

For an existing authoritative project with a pending migration, use this order:

1. Create and independently verify a `pre-migration` backup while the existing
   PostgreSQL schema remains reachable.
2. Stop the ClearSpend server so no dashboard write can race the migration.
3. Run admin `status`, then `migrate`.
4. Run `runtime-status`, restart the server, check `/api/health`, and perform
   representative dashboard reads and writes.

Never apply an authoritative migration merely because `runtime-status` reports
an older version. Backup creation, review, and explicit approval remain required.

## Private local state

- Authoritative database: private Supabase PostgreSQL `clearspend` schema
- Runtime configuration: ignored file under `data/`
- Project CA certificate: ignored file under `data/certificates/`
- Archival SQLite snapshot: `data/clearspend.db`
- PostgreSQL backups: `data/backups/postgresql/`
- Other private research and exports: ignored paths under `data/`

None of these files belongs in Git.

## PostgreSQL backups

Each successful backup publishes a required pair:

```text
clearspend-<label>-<timestamp>.dump.enc
clearspend-<label>-<timestamp>.dump.enc.integrity
```

The first file is the encrypted `pg_dump` archive. The second contains versioned
PBKDF2 and HMAC-SHA-256 metadata. Both are mode `0600`, and both are required for
restore. The integrity check is keyed by the separate archive passphrase and is
verified before any restore decryption begins.

Keep the pair together. Upload both files manually to the approved private
off-device folder and confirm their filenames and sizes. Never upload the
archive passphrase, Keychain export, plaintext dump, SQLite database, or source
statements beside them. No automatic retention or deletion policy is enabled;
keep all backup pairs until a later explicit policy replaces this rule.

Create a standalone backup with the restricted runtime credential:

```bash
PYTHONPATH=src:. .venv/bin/python -m clearspend.admin backup \
  --runtime-config data/postgresql-runtime.json \
  --label manual
```

Success prints the new `.dump.enc` path after encryption, structural listing,
and integrity publication have all succeeded. Failure removes partial output.

Authenticate and structurally inspect an existing pair without contacting the
database:

```bash
PYTHONPATH=src:. .venv/bin/python -m clearspend.admin verify-backup \
  --runtime-config data/postgresql-runtime.json \
  --archive data/backups/postgresql/clearspend-manual-TIMESTAMP.dump.enc
```

This requires the matching `.integrity` file and archive-passphrase Keychain
item. It verifies the HMAC before decryption and confirms that the archive lists
every maintained table. It never writes database state.

Archives created before keyed integrity files were introduced remain private
historical artifacts, but the maintained restore path rejects them because it
cannot authenticate them. After deploying this version, create and upload a new
verified backup pair before relying on the updated recovery path. Do not delete
older archives merely to clean the directory.

## Automatic pre-import backup

Staging and preview are read-only. An approved PostgreSQL import:

1. acquires the application-wide PostgreSQL write lock;
2. creates and verifies the encrypted backup pair;
3. writes merchant decisions, transactions, links, exclusions, overrides,
   coverage, and audit rows in one transaction; and
4. commits everything or rolls everything back.

Every ordinary dashboard mutation uses the same transaction-scoped lock, so it
cannot commit between the pre-import recovery point and the import commit.

After an import, upload the new backup pair off-device and compare the staged
preview with the committed audit result, affected counts, totals, coverage, and
representative dashboard output.

## Restore authoritative PostgreSQL

Restore changes authoritative financial state and requires explicit approval.

1. Stop the ClearSpend server.
2. Preserve the current PostgreSQL state if it remains reachable.
3. Select the exact `.dump.enc` archive, its matching `.integrity` file, and the
   separately stored archive passphrase.
4. Create an approved replacement Supabase project, but do not provision the
   `clearspend` schema or run migrations. Configure its admin and intended
   runtime credentials in the ignored files and Keychain.
5. Run the maintained restore command:

   ```bash
   PYTHONPATH=src:. .venv/bin/python -m clearspend.admin restore \
     --admin-config data/postgresql-admin.json \
     --runtime-config data/postgresql-runtime.json \
     --archive data/backups/postgresql/clearspend-LABEL-TIMESTAMP.dump.enc
   ```

   The command first confirms that the private schema is absent, bootstraps only
   the restricted runtime role needed by restored grants, verifies backup
   integrity, restores in one transaction, reapplies the private-schema
   security boundary, and verifies the current migration history. A failure
   before schema creation leaves only the restricted role and may be retried
   after correction. A failure after the target changes must not be retried
   blindly: keep the server stopped, inspect the recovery environment, and
   either complete provisioning or replace the failed target under explicit
   approval.
   Success reports that restore and runtime security verification completed and
   prints the restored schema version.
6. Verify runtime permissions, representative reads and writes, counts,
   relationships, and dashboard results.
7. Update the ignored runtime configuration only after verification.
8. Restart ClearSpend and check `/api/health` plus representative workflows.

Do not restore PostgreSQL activity into SQLite. After PostgreSQL became
authoritative, the SQLite snapshot became archival and is not a rollback target.
Git also contains no financial recovery copy.

## Provisioning a replacement environment

Do not run the ordinary `provision` and `migrate` commands before restoring a
backup: provisioning creates the private schema, while restore deliberately
requires that schema to be absent. The combined `restore` command owns the
replacement sequence. Use `provision` followed by `migrate` only for a new,
empty installation that will not receive an existing backup. The application
server must remain stopped until restore and verification are complete.

Do not expose the private schema through the Supabase Data API. The browser
continues to communicate only with the local Python API.

## Import incident response

If an approved import is wrong, stop further imports and preserve the current
state. Prefer a targeted audited correction when the imported rows are valid but
a category or mapping is wrong. Restore the pre-import PostgreSQL backup only
when the batch itself must be rolled back, and only after separately preserving
the current database for comparison.

Review:

- provider, filename, timestamp, cards, and coverage dates;
- inserted, duplicate, pending, excluded, and outside-cycle counts;
- parsed totals against official statement totals;
- unresolved merchant decisions and representative inserted rows; and
- affected dashboard totals and latest transaction dates.

## Moving ClearSpend to another computer

### Existing Supabase project on a new Mac

1. Clone the application and create its virtual environment.
2. Transfer the ignored runtime configuration and approved CA certificate over
   a private channel, or recreate the runtime file from the tracked template.
3. Create the runtime database and backup-passphrase Keychain items.
4. Run `clearspend.admin runtime-status`.
5. Start the local server, verify `/api/health`, and check representative
   dashboard reads. No database restore or SQLite transfer is required.

### Replacement Supabase environment

1. Create a new project and keep the ClearSpend server stopped.
2. Prepare both ignored configurations, the CA certificate, and all three
   Keychain items.
3. Run `verify-backup` against the selected encrypted pair.
4. Run the combined `restore` command against the schema-empty project.
5. Verify permissions, counts, relationships, representative reads and writes,
   then run `runtime-status`.
6. Start the server and verify `/api/health` and representative workflows.

The archival SQLite snapshot is not a recovery source after PostgreSQL became
authoritative. Never commit configuration, credentials, statements, SQLite
snapshots, or backups.
