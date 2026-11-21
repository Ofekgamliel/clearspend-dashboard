# PostgreSQL architecture decision

## Status

Accepted. PostgreSQL is the authoritative ClearSpend database. The previous
SQLite database is an archival snapshot, not a rollback target after normal
PostgreSQL use began.

## Context

ClearSpend remains a local, single-user dashboard, but an authoritative database
stored only on one computer created avoidable availability and recovery risk.
The application needed managed storage without exposing the dashboard itself or
moving financial logic into a browser-facing cloud API.

## Decision

ClearSpend uses a private Supabase PostgreSQL project while retaining the Vue
frontend and Python server on the user's computer.

- The browser communicates only with the local ClearSpend HTTP API.
- The Python server connects through TLS using a small bounded pool and the
  restricted `clearspend_app` role.
- Application objects live in the private `clearspend` schema.
- Explicit migrations create objects, grant only required runtime privileges,
  and deny Supabase API roles access to the private schema.
- The Supabase Data API remains disabled because ClearSpend does not use a
  browser-to-database path.
- Administrative provisioning and migration credentials are never supplied to
  the running application.
- Database and backup passwords currently live in macOS Keychain. A generalized
  secret-provider abstraction is deferred while ClearSpend remains a local
  macOS application.

## Write and backup boundary

All ordinary PostgreSQL feature writes acquire the same transaction-scoped
advisory lock. Approved imports acquire that lock before creating their
pre-import backup and hold it until the import commits or rolls back. This
prevents another dashboard mutation from committing between the recovery point
and the import transaction.

PostgreSQL backups consist of an encrypted custom-format dump and its matching
keyed integrity file. Restore verifies HMAC-SHA-256 before decryption, restores
only into an approved empty target, and verifies the maintained schema and
migration history afterward. Both files are stored together; the passphrase is
kept separately in Keychain. Off-device copies remain private and are uploaded
manually until an automated storage policy is approved.

## Consequences

- PostgreSQL is the only normal reader and writer; there is no automatic SQLite
  fallback.
- A PostgreSQL outage makes the dashboard unavailable rather than silently
  accepting writes elsewhere.
- Disaster recovery uses PostgreSQL backups. The archival SQLite snapshot is
  retained for historical inspection only.
- Provisioning, migrations, permissions, backup creation, and restore remain
  maintained application capabilities.
- One-time copy, parity, benchmarking, and cutover rehearsal utilities are not
  part of the permanent production surface.
- Real PostgreSQL execution in CI is deferred. Current CI uses synthetic tests;
  future PostgreSQL CI must use a disposable isolated service and never the
  private Supabase project.
