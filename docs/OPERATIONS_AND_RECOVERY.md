# Operations, backups, and recovery

This document covers normal startup, PostgreSQL backups, import recovery, and
safe movement of ClearSpend's private state. Run commands from the repository
root.

## Start and stop

Start the local application with the ignored PostgreSQL runtime configuration:

```bash
PYTHONPATH=src:. .venv/bin/python -m clearspend.server \
  --postgresql-config data/postgresql-frankfurt-runtime.json \
  --port 8765
```

Keep that process running while using ClearSpend and stop it normally with
`Ctrl-C`. Restart it after switching Git branches so the server and generated
frontend come from the same checkout.

Open `http://localhost:8765` and check
`http://localhost:8765/api/health` when troubleshooting. A compatible response
reports `status: ok`, `database: true`, and the API compatibility identifier
expected by the frontend.

The retained SQLite file is an archival pre-PostgreSQL snapshot. Omitting
`--postgresql-config` selects legacy SQLite mode, which must not be used for
normal reads, edits, or imports. PostgreSQL failure never triggers an automatic
SQLite fallback.

If port 8765 is occupied, inspect it before stopping anything:

```bash
lsof -nP -iTCP:8765 -sTCP:LISTEN
```

Do not terminate an unknown process.

## Runtime configuration and secrets

The ignored runtime configuration contains endpoint metadata, explicit CA and
tool paths, local-state and backup directories, and macOS Keychain item names.
It must not contain database or archive passwords.

Keep the Supabase CA certificate under ignored `data/certificates/` and use TLS
`verify-full`. The server opens the restricted pool and verifies the current
schema before binding. The running application uses only the `clearspend_app`
credential; provisioning and recovery use a separate administrative credential.

macOS Keychain is the currently supported secret store. A generalized provider
is deferred while ClearSpend remains a local macOS application.

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
4. Provision an approved empty replacement PostgreSQL environment.
5. Run the maintained restore operation. It must verify the keyed integrity
   file before decryption, refuse an occupied target, restore in one transaction,
   and verify the schema and migration history.
6. Verify runtime permissions, representative reads and writes, counts,
   relationships, and dashboard results.
7. Update the ignored runtime configuration only after verification.
8. Restart ClearSpend and check `/api/health` plus representative workflows.

Do not restore PostgreSQL activity into SQLite. After PostgreSQL became
authoritative, the SQLite snapshot became archival and is not a rollback target.
Git also contains no financial recovery copy.

## Provisioning a replacement environment

Use the maintained PostgreSQL provisioning and migration modules with the
administrative `postgres` connection. Provisioning creates and verifies the
private schema and restricted runtime role; migrations create application
objects and grant exact runtime permissions. The application server must remain
stopped until restore and verification are complete.

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

Clone the application repository and create its virtual environment. Transfer
the ignored runtime configuration and CA certificate through an approved private
channel, create the required Keychain items on the new Mac, and transfer a
verified PostgreSQL backup pair only when recovery is required. Never commit
configuration, credentials, statements, SQLite snapshots, or backups.
