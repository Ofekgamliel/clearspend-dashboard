# SQLite to Supabase PostgreSQL migration plan

## Status and scope

This is the maintained implementation record for moving ClearSpend's
authoritative financial state from the local SQLite file to a Supabase-hosted
PostgreSQL database. The controlled production cutover was explicitly approved
and completed on 2026-11-21. PostgreSQL is now authoritative; the final SQLite
database is an archival snapshot and is not a runtime fallback.

The Vue frontend and Python application server remain local during this project.
Only the database becomes remote:

```text
Vue browser
  -> local ClearSpend Python server
  -> encrypted PostgreSQL connection
  -> Supabase PostgreSQL
```

This does not make the dashboard accessible from another computer or phone.
Remote dashboard access would be a separate project covering backend hosting,
user authentication, HTTPS, access control, and hosted secret management.

Implementation and testing proceed one feature at a time. Production data does
not. The final production migration uses a controlled maintenance window and
switches all reads and writes from SQLite to PostgreSQL together.

## Goals

- Remove the local SQLite file as the only authoritative copy of financial
  state.
- Preserve existing HTTP contracts, financial calculations, import identities,
  mappings, overrides, reimbursements, events, recurring decisions, and
  observation reviews.
- Keep the dashboard and Python server local.
- Add the smallest database portability boundary consistent with
  `ARCHITECTURE.md`.
- Run the same synthetic feature and API behavior against SQLite and
  PostgreSQL.
- Rehearse and verify a complete relational copy before production cutover.
- Preserve a tested recovery path and an independent encrypted backup.
- Measure whether remote-database latency remains acceptable for normal
  ClearSpend use.

## Non-goals

- Hosting the dashboard or Python API publicly.
- Adding a ClearSpend user-login screen.
- Allowing Vue or generated frontend assets to connect to Supabase directly.
- Replacing feature modules with generic repositories.
- Running SQLite and PostgreSQL as independent production writers.
- Maintaining a production replication outbox unless uninterrupted writes later
  become an explicit requirement.
- Changing financial rules, reporting scope, observation thresholds, or API
  response shapes.
- Opportunistically redesigning stored amount, date, or JSON types during the
  initial engine migration.
- Copying private data merely because automated tests pass.

## Decisions established by this plan

1. Supabase PostgreSQL is the target remote database.
2. The backend remains local for this project.
3. The browser continues to use only the local ClearSpend HTTP API.
4. The `clearspend_app` credential remains in the Python backend and never
   reaches Vue; the Supabase `postgres` credential is available only to
   explicit offline migration and recovery tooling.
5. SQLite remained authoritative until the global maintenance-window cutover.
6. PostgreSQL became authoritative for all reads and writes together.
7. PostgreSQL unavailability after cutover is an application outage, not a
   reason to write automatically to SQLite.
8. The final SQLite snapshot is a pre-resume fallback only. After normal
   PostgreSQL use resumes, it is a read-only archive and cannot become active.
9. Feature-owned SQL remains in its existing feature package.
10. The staged statement import is the final and most stringent workflow
    verified before cutover.

If uninterrupted use becomes a requirement, a durable replication design must
be reviewed as a separate expansion of this plan. Best-effort dual writes are
never acceptable.

## Current database architecture

### Runtime path

The current request path is:

```text
Vue feature
  -> frontend/src/api
  -> clearspend/http
  -> feature query or service
  -> clearspend/database/connection.py
  -> data/clearspend.db
```

`database/connection.py` returns a raw `sqlite3.Connection`. Feature query and
service modules execute SQL directly on that connection. Most API operations
open and close a connection within one request. The staged-import repository
keeps one connection for the complete approved commit transaction.

The frontend has no direct database dependency. The database migration should
not require frontend transport or TypeScript contract changes.

### Persisted tables and ownership

| Tables | Primary owner | Important consumers |
| --- | --- | --- |
| `schema_migrations` | `database/` | Migration inspection and verification |
| `imports`, `import_transactions`, `import_coverage` | `imports/`, `staging/` | Dashboard audit context, mapping review |
| `transactions` | `imports/` for insertion | Reporting, transactions, merchants, recurring, events, observations, staging |
| `merchant_mappings` | `merchants/`, staged decisions | Imports, reporting, management |
| `merchant_display_mappings` | `merchants/`, staged decisions | Transactions, recurring, events, observations |
| `transaction_category_overrides` | `transactions/`, staged decisions | Dashboard, categories, events, recurring, observations |
| `transaction_spending_adjustments` | `transactions/` | Personal-spending calculations throughout reporting |
| `income_imports`, `income_entries` | `imports/` | Dashboard, trends, amount-left reporting, observations |
| `recurring_profiles`, `recurring_profile_members` | `recurring/` | Merchants and observations |
| `observation_reviews` | `observations/` | Observation reads and reversible reviews |
| `events`, `event_transactions` | `events/` | Transactions, reporting scope, categories, observations |

`transactions` is the central dependency. The complete relational dataset
must exist in PostgreSQL before any production feature can use it.

### Current write transactions

| Workflow | Tables changed together |
| --- | --- |
| Statement import | Import audit, transactions, duplicate links, coverage, merchant decisions, category overrides |
| Income import | Income import audit and income entries |
| Merchant mapping | Merchant mapping and matching transaction category fields |
| Display identity management | Display mappings, optional category mappings, matching transaction fields |
| Transaction correction | One category override |
| Reimbursement | One spending adjustment |
| Event management | Event identity/settings or one exact transaction membership |
| Recurring management | Profile and reviewed alias membership |
| Observation review | One reversible structured review record |

The statement-import boundary remains non-negotiable: backup, reviewed
decisions, transactions, duplicate links, coverage, and audit results must
succeed or fail as one operation.

### SQLite-specific behavior to remove or isolate

- `sqlite3.Connection`, `sqlite3.Row`, and `sqlite3.IntegrityError`
- `?` bind parameters
- `PRAGMA foreign_keys` and `PRAGMA integrity_check`
- `sqlite_master` and `PRAGMA table_info` schema inspection
- SQLite's online backup API
- `BEGIN IMMEDIATE`
- `lastrowid`
- `INSERT OR IGNORE` and `INSERT OR REPLACE`
- SQLite scalar `MAX(value, 0)` behavior
- `substr(...)` and string concatenation in reporting-date expressions
- SQLite null comparisons such as `IS ?`
- The trigger that applies reviewed merchant mappings after transaction insert
- Local file assumptions in database, backup, and staging operations

Runtime SQLite connections currently leave foreign-key enforcement disabled
unless a caller opts in. PostgreSQL enforces declared foreign keys. An orphan
and constraint audit is required before the first private rehearsal.

## Target data-layer architecture

The target is a mechanical database boundary, not a repository for every table:

```text
Feature query/service
        |
        v
Database settings + session/transaction contract
        |
        +-- SQLite adapter
        |
        +-- PostgreSQL adapter
```

### Database infrastructure responsibilities

`clearspend/database/` will own:

- Backend selection and configuration
- Opening, pooling, and closing connections
- Session and transaction primitives
- Bind-parameter and returned-row conventions
- Connection-failure handling
- Mechanical dialect helpers where SQL cannot be shared safely
- Backend-specific schema migrations and verification
- Backup and restore orchestration
- Redaction of credentials from database errors and diagnostics

### Feature responsibilities that do not move

- Reporting queries and totals remain under `reporting/`.
- Transaction reads and writes remain under `transactions/`.
- Merchant identity/category behavior remains under `merchants/`.
- Recurring behavior remains under `recurring/`.
- Events remain under `events/`.
- Observation qualification remains under `observations/`.
- Provider parsing remains under `imports/`.
- Approved import orchestration remains under `staging/`.
- HTTP modules continue to decode requests and map errors; they do not gain SQL.

Shared infrastructure may normalize connection and cursor mechanics. It must
not absorb financial rules, feature queries, import decisions, or observation
policy. Separate SQLite and PostgreSQL statements are acceptable where
dialects genuinely differ, but both remain owned and tested by the feature.

## Supabase connection and isolation design

### Driver and pooling

Psycopg 3.2.13 with `psycopg-pool` 3.2.8 is the selected driver stack. These
are the final release lines supporting ClearSpend's current Python 3.9 runtime;
Psycopg 3.3 requires Python 3.10 or newer. The local threaded server will use a
small bounded application connection pool rather than creating an unbounded
number of remote connections.

The initial implementation must configure and test only:

- A small maximum pool size
- A connection acquisition timeout
- A SQL statement timeout
- One acquired connection for each complete transaction, including an approved
  import commit; do not hold it across the in-memory staging session
- Guaranteed rollback and connection release after failure
- A clear unavailable or busy error when a connection cannot be acquired
- Discarding a broken connection instead of returning it to the pool

The initial acquisition and connection timeout is 15 seconds. A 5-second
setting failed during the first hosted Session-pooler smoke check before any
SQL ran; the selected region and pooler can take longer to establish a new
connection. Statement execution retains its separate 15-second timeout.

Pool size is selected from measurement, not production-scale assumptions.
Connection lifetime policies, proactive health checks, lock timeouts,
idle-in-transaction timeouts, and more detailed exhaustion handling are added
only if testing or operation reveals a concrete problem.

### Connection modes

- The current ClearSpend network resolves the direct endpoint but has no IPv6
  route to it. Initial runtime traffic therefore uses the shared pooler in
  session mode. Recheck this before cutover in case the network changes.
- Transaction-pooler mode is not the default because ClearSpend uses ordinary
  persistent-backend behavior and may require prepared statements or session
  state.
- A direct connection remains preferred for schema migrations, `pg_dump`,
  restore, and administrative verification. The current free-tier project and
  local network do not provide a usable direct IPv6 route, so the shared pooler
  in session mode is the approved exception for transactional provisioning and
  schema migrations. Transaction-pooler mode is not approved. A custom-format
  dump of the prepared empty schema has been restored successfully through this
  session-mode path into an isolated local PostgreSQL database. The separate
  application-owned encrypted recovery path has also completed a full
  representative synthetic-data rehearsal against isolated local TLS targets.
- The selected modes and reasons are recorded before private data is copied.

### Private schema and roles

Application objects live in a dedicated `clearspend` schema, not `public`.
The schema is not added to the Supabase Data API exposed-schema list.

Required privilege boundary:

- Revoke schema access from `PUBLIC`.
- Grant no ClearSpend schema access to `anon`, `authenticated`, or
  `service_role`.
- Create the dedicated `clearspend_app` login role for the Python runtime.
- Grant `clearspend_app` only required `SELECT`, `INSERT`, `UPDATE`,
  `DELETE`, and sequence privileges.
- Do not let `clearspend_app` own, create, alter, or drop schema objects.
- Use the Supabase `postgres` role for explicit migrations, provisioning, and
  recovery only.
- Store the `postgres` credential separately and never make it available to the
  running application.
- Set a restricted explicit `search_path` or use schema-qualified objects.

Do not use `ALTER DEFAULT PRIVILEGES`. Each migration creates its objects,
grants `clearspend_app` the exact required schema, table, sequence, and function
permissions, and verifies those grants. If a migration creates a function, it
explicitly revokes `EXECUTE` from `PUBLIC` when the function is not intended to
be public. `anon`, `authenticated`, `service_role`, and `PUBLIC` receive no
ClearSpend data access.

RLS is not the primary boundary for this architecture because the browser does
not use the Data API. Schema isolation, grants, and the dedicated database role
are authoritative.

### TLS

- Enable Supabase SSL enforcement for incoming PostgreSQL connections.
- Download and protect the project CA certificate.
- Configure Psycopg with `sslmode=verify-full` and the approved CA.
- Do not treat `sslmode=require` as full server-identity verification.
- Test invalid, missing, and replaced certificates.

### Region

The Supabase project was created in the automatically selected
`ap-southeast-2` region. Before the project receives private data, benchmark
that region from the network where ClearSpend runs and confirm that its latency
and financial-data location are acceptable. Moving regions later is treated as
another database migration.

## Data representation and minimization

The first PostgreSQL schema prioritizes behavioral parity over cleanup:

- Preserve primary keys and advance PostgreSQL sequences beyond copied IDs.
- Preserve `transaction_key`, `base_key`, `entry_key`, hashes, and finding
  keys exactly.
- Preserve required provider evidence and duplicate-detection inputs.
- Preserve amount precision; do not round-trip evidence through binary floating
  point.
- Preserve existing ISO date/month semantics before separately considering
  native PostgreSQL types.
- Preserve JSON meaning and deterministic comparisons before considering
  `jsonb`.
- Preserve independent mapping, identity, override, reimbursement, event,
  recurring, and review concepts.

The migration intentionally includes the existing financial database. A full
classification of every persisted column is not required. Before the first
private copy, review only fields whose operational detail or sensitivity makes
their value questionable:

- `source_path`
- Statement filenames
- Stored error messages
- Raw `source_payload`
- Temporary or staging-derived metadata

All other stored fields are intentionally migrated because they support the
financial record, audit trail, durable identity, duplicate detection, or
application behavior. Before normalizing or excluding a questionable field,
verify that imports, duplicate detection, troubleshooting, and audit behavior
do not depend on it. Required evidence remains intact. Local filesystem details
with no audit purpose may be normalized or excluded only through an explicit,
tested migration decision. A `NOT NULL` column is not removed or rewritten
casually.

Approved decision: preserve statement filenames; replace each full
`source_path` with that filename; do not copy stored error messages or raw
`source_payload`; and do not persist temporary staging metadata. The backend
uses the same policy for future PostgreSQL writes while retaining the legacy
SQLite behavior until cutover. Detailed parse failures may still be returned to
the active local request, but they are not stored in PostgreSQL.

Conversions to `numeric`, `date`, `timestamptz`, `jsonb`, generated
columns, or PostgreSQL-specific indexes are later migrations with independent
verification.

## Migration model

There is no continuous production replication in the default plan.

```text
Before maintenance: SQLite is the sole reader and writer
During maintenance: mutations are stopped; data is copied and verified
After cutover:       PostgreSQL is the sole reader and writer
Archived snapshot:  SQLite is retained read-only after normal use resumes
```

Portability is incremental in code and tests. Production authority is not
incremental.

## Implementation stages

### Stage 1: Architecture decisions and baseline

- Confirm the local backend and remote-database-only scope.
- Record the clean SQLite synthetic and frontend baselines.
- Inventory database-opening calls, SQL owners, and transaction boundaries.
- Select Psycopg version, pool implementation, and initial pool limits.
- Record session-pooler runtime connectivity for the current IPv4-only network,
  the approved session-mode provisioning/migration exception, and the separate
  backup/restore rehearsal requirement.
- Select the schema name and exact `clearspend_app` grant policy.
- Select Keychain-backed secret loading.
- Benchmark and approve the selected `ap-southeast-2` Supabase region.
- Define connection and statement timeouts.
- Decide whether free-tier pausing is acceptable for the authoritative
  database.
- Define recovery objectives, backup destination, encryption, and retention.
- Record SQLite timings for the representative performance workflows used in
  Stage 4; numeric thresholds for every endpoint are not required.

Exit gate: all architectural and operational decisions are recorded without
creating a private production database.

Temporary backup decision: write encrypted archives to the ignored local
`data/backups/postgresql/` directory and manually upload them to a private
Google Drive folder. No automatic pruning is enabled. This is acceptable for
continued synthetic and runtime testing. The later verified off-device upload,
recoverable archive-key procedure, and explicit retention policy satisfied the
cutover gate.

The first encrypted empty-schema archive has now been manually uploaded and its
filename and size confirmed. The explicit interim retention policy is to keep
every encrypted local and Drive copy with no automatic deletion. The
independent archive key now has a separately confirmed password-manager copy in
addition to its macOS Keychain working copy. The backup, retention, and
key-recovery preparation gate is complete.

### Stage 2: Database portability

- Introduce the minimal backend-neutral settings, session, cursor, and
  transaction contract.
- Route current SQLite behavior through an SQLite adapter without changing API
  responses.
- Add Psycopg, a bounded PostgreSQL pool, and the PostgreSQL adapter.
- Add backend-specific schema migrations, explicit per-migration grants, and
  verification.
- Keep feature-owned SQL in existing query and service modules.
- Port features in dependency-aware order:
  1. Observation reviews
  2. Transaction reads, category overrides, and reimbursements
  3. Merchant mappings and display identities
  4. Events and exact transaction membership
  5. Recurring profiles and membership
  6. Category and shared reporting scope
  7. Dashboard reporting and income
  8. Observation input assembly and installment reads
  9. Staged analysis, duplicate detection, imports, and coverage
- Add SQLite/PostgreSQL test-matrix coverage.
- Keep all production runtime configuration on SQLite.

Implementation note: the merchant-management migration creates the
statement-coverage and recurring-profile tables because the existing merchant
read model requires them. This does not port recurring edits or approved import
writes early. Recurring edits and membership are now ported in step 5; approved
import and coverage writes remain in step 9. Hosted synthetic checks have
verified merchant rule history, the future-insert trigger, independent display
identity/category decisions, and mapping context through the restricted runtime
role.

The event slice reuses the event schema and grants created by migration 2, so it
does not add an empty schema migration. Its feature-owned queries and services
now use the shared database boundaries. Hosted synthetic checks have verified
event creation, exact assignment, scoped reads, settings edits that preserve
membership, and unassignment through the restricted runtime role.

The recurring slice reuses the profile and membership schema created by
migration 3, so it also does not add an empty schema migration. Hosted synthetic
checks have verified exact alias selection, month-scoped series reads, lifecycle
editing, and membership preservation when a profile is marked not recurring.

The category and shared reporting-scope slice requires no schema migration. Its
feature-owned aggregation now uses the shared database boundary and portable
numeric SQL, while the existing pure scope builder remains authoritative for
period, card, and event filtering. Hosted synthetic checks have verified
month-over-month category comparison, selected-card scope, and routine-only
event exclusion.

The dashboard reporting and income slice reuses the income schema and sequence
grants created by migration 2, so it does not add an empty schema migration.
Its read model now uses the shared database boundary, portable aggregation SQL,
and JSON-safe numeric normalization. Hosted synthetic checks have verified
spending, refunds, household income and balance, card totals, coverage months,
and month/year trends.

The observation-input and installment-read slice requires no schema migration.
The composed loader now forwards the shared database target to its ported
dashboard, transaction, recurring, review, and dedicated installment reads.
Hosted synthetic checks have verified historical scope, income visibility,
month-indexed transactions, stable installment-plan evidence, and active review
state.

Import portability progress: migration 4 adds the private
`import_transactions` linkage and hosted synthetic checks verify staged
references, nullable duplicate matching, coverage analysis/upserts, and linkage
access through `clearspend_app`. The import repository now uses portable
returned identities and conflict handling on a caller-owned connection; a real
PostgreSQL rehearsal verified statement and income persistence, duplicate
linkage, metadata minimization, and connection ownership. The full reviewed
write sequence is now portable and composed with an advisory transaction lock
and encrypted pre-import backup. A real bounded-pool TLS rehearsal using
`clearspend_app` proved that the archive contained zero pre-import rows and the
new row appeared only after commit. Server selection is now explicit and
fail-closed through an ignored `--postgresql-config` file: startup opens the
restricted pool and verifies the current schema before binding, while SQLite
remains an explicit legacy command-line mode with no fallback. The real-data
cutover, off-device storage, retention, and recoverable-key gates are complete;
the SQLite commit path remains available only for compatibility testing and
archival inspection.

Exit gate: all synthetic feature and API scenarios pass on both engines with
equivalent normalized results.

### Stage 3: Synthetic Supabase verification

- Create a Supabase environment containing no private financial data.
- Create the private schema and `clearspend_app` through the Supabase `postgres`
  connection.
- Verify each migration's explicit grants, lack of Data API exposure, and
  restricted `search_path`; prove `clearspend_app` receives only its intended
  access and API roles and `PUBLIC` receive none.
- Verify SSL enforcement and `verify-full` certificate behavior.
- Verify the selected direct or session-pooler runtime connection and its basic
  pool and timeout configuration.
- Run schema creation and migrations, representative reads and writes, and
  Supabase security/advisor checks.
- Create and restore a verified backup.
- Perform one basic remote-unavailability check and prove the application fails
  clearly without silently falling back to SQLite.

Exit gate: the hosted synthetic environment passes the required permission,
TLS, runtime connection, schema, backup/restore, representative read/write,
security, and basic unavailability checks.

Current recovery evidence: the hosted empty schema was dumped through the
session pooler and restored into an isolated PostgreSQL 17 database. The
restore recovered 16 tables, migration versions 1 through 4, administrative
ownership, explicit runtime grants, and the expected restricted privileges;
the temporary recovery artifacts were removed. This proves the connection and
logical archive format. The application now has an archive creator that streams
`pg_dump` through
encryption, uses independent Keychain credentials, verifies the decrypted
archive inventory, and removes partial output on failure. Its synthetic-tested
restore path refuses an occupied target, restores in one transaction without a
plaintext intermediate, and verifies all expected tables and migration rows.
The complete linked 15-table fixture has now passed this real encrypted path
between two isolated TLS PostgreSQL 17 clusters. Exact table hashes, all four
migrations and sequences, minimization, and runtime/API-role permissions were
preserved; an occupied-target retry was refused. All temporary artifacts were
removed. The runtime configuration and approved-import hook are implemented.
The project CA and explicit runtime startup check are now verified through the
restricted Session-pooler role. The first encrypted empty-schema archive was
manually uploaded to the private off-device destination and its filename and
size were confirmed. The keep-all interim retention policy is explicit. The
archive key has a separate password-manager recovery copy in addition to its
Keychain working copy. The temporary local destination remains
`data/backups/postgresql/`. The private-data copy was subsequently approved,
completed, and verified. A populated encrypted archive was then created with
complete decryption and required-table inventory verification and manually
uploaded to the private off-device destination. Its filename and size were
confirmed; the local copy remains mode `0600` under the keep-all policy.

### Stage 4: Copy-tooling and rehearsal

Build one deterministic migration tool that:

1. Opens SQLite consistently and read-only.
2. Audits orphaned references and constraint compatibility.
3. Applies the reviewed data-minimization decisions.
4. Creates and verifies the PostgreSQL schema.
5. Copies all tables in dependency order while preserving identities.
6. Advances PostgreSQL sequences.
7. Compares schema, relationships, counts, hashes, financial totals, and
   normalized API payloads.
8. Prints only generic status, counts, identifiers safe for logs, and hashes.

Rehearse first with disposable synthetic SQLite data.

Current copy-tooling evidence: the deterministic copier now opens SQLite
query-only, checks schema/integrity/foreign keys, requires an empty migration-4
target, copies all 15 data tables atomically in dependency order, preserves and
advances identities, and verifies ordered counts and SHA-256 content hashes.
Its complete disposable PostgreSQL rehearsal copied one linked synthetic row
through all 15 application data tables and verified relationships, explicit
metadata redaction, all four identity sequences, counts, hashes, runtime
readability, and API-role denial. The temporary SQLite source, PostgreSQL
database, and server cluster were removed. The data-minimization policy is now
approved and encoded in both copy and future-import persistence. The synthetic
copy-fixture and backup/recovery gates are complete. The private-data copy was
explicitly authorized and completed while the server was stopped.

The cross-engine financial verifier now compares exact normalized presentation
hashes without logging payload values. It covers every dashboard calculation
section, the dashboard's recent-transaction presentation, complete transaction
rows and ordering, every month plus year/all-time scopes, representative card
scopes, one real search and category filter, and earliest/middle/latest plus
year/all-time financial observations. This bounded matrix avoids repeatedly
rebuilding the full historical observation dataset for every month. Its
command-line wrapper also proves that the SQLite source file is unchanged. The
approved private copy preserved 5,074 rows across 15 application data tables.
The populated PostgreSQL target and untouched SQLite source then passed all 802
deterministic financial and presentation comparisons, and the verifier
confirmed that the SQLite source file was unchanged.

Measure SQLite and PostgreSQL behavior for:

- Initial dashboard load
- Month and card changes
- Complete-history transaction search
- Financial observation generation
- Import preview
- One representative approved import

Record comparable SQLite and PostgreSQL timings for these workflows. The
PostgreSQL version must complete without timeouts or database errors and remain
comfortable for normal dashboard use. Investigate meaningful regressions;
inspect query counts, connection acquisition, and pool state only as needed to
diagnose them. Consolidate queries or add indexes only where an actual slowdown
appears.

Current read-performance evidence does not pass this gate. Against the Sydney
Session pooler, representative PostgreSQL timings were approximately 6.5--7.3
seconds for dashboard load/month/card changes, 1.9--2.1 seconds for transaction
search, and 59.7--63.4 seconds for monthly financial observations. Equivalent
SQLite timings were below 0.2 seconds. Safe instrumentation counted 19
sequential PostgreSQL queries per dashboard workflow, 4 for search, and 129 for
the observation workflow. The SQLite source remained unchanged and no database
error or timeout occurred. Import preview and approved-import performance
checks remain deferred until the read latency is resolved; no performance
indexes are justified by this evidence because round-trip count and geographic
distance dominate.

The project was therefore rehearsed again in Frankfurt (`eu-central-1`) while
the Sydney project remained untouched. Provisioning recreated the restricted
runtime boundary, migrations 1 through 4 applied and verified, and the offline
copy again produced 15 tables, 5,074 rows, and the same combined content hash.
All 802 financial and presentation comparisons passed with the same snapshot
hash, and SQLite remained unchanged. A populated Frankfurt archive passed full
decryption and required-table inventory verification and is awaiting confirmed
off-device upload.

Frankfurt reduced representative dashboard actions to approximately 1.35--1.47
seconds, search to approximately 0.41 seconds, and monthly observations from
approximately 60 seconds in Sydney to 12.5 seconds. The remaining observation
delay justified consolidating complete transaction history from one four-query
read per month into one unbounded internal history read while preserving the
browser's 1,000-row browse limit. After consolidation, observations completed
in approximately 4.47 seconds with 49 queries instead of 129. All 426 synthetic
tests and all 802 cross-engine comparisons passed, and the combined presentation
snapshot hash remained unchanged. The read-performance gate is now satisfied;
the remaining import and server checks then completed successfully. A synthetic
XLSX preview completed in approximately 0.94 seconds. Its approved import
created and fully verified an encrypted pre-import archive, acquired the import
lock, committed one synthetic transaction in approximately 9.31 seconds, and
then removed all synthetic rows. All 15 table counts returned to baseline and a
post-cleanup run passed all 802 comparisons with the original snapshot hash.
The SQLite file remained unchanged. A temporary PostgreSQL server on port 8770
returned HTTP 200 with valid response shapes for health, dashboard,
transactions, and observations, served the built dashboard shell, and was then
stopped with the port confirmed inactive. The representative rehearsal and
performance gate is complete.

Exit gate: repeated rehearsals are deterministic, private rehearsal cleanup is
verified, parity is exact where required, and the representative workflows
remain comfortable to use without disruptive regressions.

### Stage 5: Prepare the operational cutover runbook

Create a separate runbook containing:

- Pre-maintenance confirmation that no staged import or write is in progress
- Python server shutdown and process/port verification procedure
- Offline-only backup, copy, and verification procedure
- Exact backup and restore checks
- Approved source and target identifiers
- Connection and role verification
- Copy command and expected generic results
- Schema, count, hash, financial, and API checks
- Performance smoke checks
- PostgreSQL configuration and server-restart procedure
- Reversible-write smoke checks
- Rollback decision points and responsible operator
- PostgreSQL backup and restore procedure for recovery after normal use resumes
- Maintenance completion criteria

The tracked template contains safe placeholders only. A completed runbook is
private when it contains project identifiers, endpoints, local paths, recovery
locations, or other operational secrets.

The tracked `POSTGRES_CUTOVER_RUNBOOK.md` now records the complete maintenance
sequence, preloaded-target eligibility checks, backup gates, temporary-server
and reversible-import checks, explicit authority decision, return-to-SQLite
path, and post-cutover recovery boundary. It contains no private worksheet
values. The complete sequence was rehearsed before the explicitly approved
normal-port start and authority transition were performed.

Exit gate: the complete runbook has been rehearsed without live authority
changes, including the pre-resume return-to-SQLite procedure and post-resume
PostgreSQL restore procedure.

### Stage 6: Controlled production cutover

This stage requires explicit approval at the time it is performed.

The maintenance boundary is a complete shutdown of the local Python server,
not a temporary application read-only mode. Staged import sessions are held in
server memory, so complete or cancel every staged import before shutdown. Do
not start the copy while any write workflow is in progress.

1. Announce the maintenance window and confirm no staged import or write
   workflow is in progress.
2. Stop the Python server completely and verify that its process and listening
   port are inactive.
3. Create and verify the final SQLite backup while the server is stopped.
4. Record the offline pre-cutover schema status, counts, relationships, and
   financial/API baselines.
5. Provision and verify the private PostgreSQL schema, `clearspend_app`, and
   its explicit grants.
6. Copy the entire relational dataset.
7. Advance PostgreSQL sequences.
8. Verify schema, constraints, relationships, counts, hashes, totals, and
   normalized API payloads.
9. Run the representative performance checks and confirm there are no
   disruptive regressions, timeouts, or database errors.
10. Configure PostgreSQL as the sole runtime database while the server remains
    stopped.
11. Restart the local Python server configured for PostgreSQL.
12. Run health and read-only smoke checks.
13. Run only the approved reversible-write checks.
14. Verify and remove or roll back the smoke writes as the runbook specifies.
15. Make the explicit continue-or-return-to-SQLite decision. Before normal use
    resumes, a failed PostgreSQL check returns to the untouched SQLite snapshot:
    stop the server, restore the SQLite runtime configuration, and restart it.
16. Explicitly end maintenance and resume normal use only after approval.
17. Preserve the final SQLite database as a read-only archival snapshot.

The maintenance decision is the authority boundary:

```text
Before normal use resumes: PostgreSQL verification failure returns to the
                           untouched SQLite snapshot.
After normal use resumes:  PostgreSQL is authoritative and recovery uses
                           PostgreSQL backups and restore procedures.
```

After normal PostgreSQL activity begins, the SQLite snapshot is archival only
and is never a rollback target. No PostgreSQL-to-SQLite reverse exporter is
required.

Exit gate: PostgreSQL is the sole authoritative database, writes are re-enabled,
and the recovery path remains valid.

Completion evidence: the maintenance-window cutover completed on 2026-11-21.
The final SQLite source passed integrity and foreign-key checks, and its private
backup matched all 15 application tables and 5,074 rows. The restricted runtime
role, private-schema boundary, four migrations, API-role denial, and client TLS
with `verify-full` all passed. The full 426-test synthetic suite and all 802
cross-engine presentation comparisons passed with the established snapshot.
The local server started on its normal port using PostgreSQL only; live health,
dashboard, transaction, observation, month/card, year-scope, calculation, and
dashboard-shell checks passed. The first encrypted post-cutover PostgreSQL
archive was structurally verified and its off-device upload was confirmed.
PostgreSQL is authoritative, and SQLite is retained only as an archival
snapshot.

### Stage 7: Stabilization

Status: active following the completed 2026-11-21 cutover.

- Monitor availability, latency, pool usage, timeouts, database errors, and
  representative financial outputs.
- Continue independent encrypted backups and restore exercises.
- Perform later operational-hardening exercises for credential rotation,
  provider pausing, and connection interruption. Add connection lifetime,
  proactive health-check, lock-timeout, idle-transaction-timeout, or detailed
  pool-exhaustion controls only if testing or operation reveals a concrete
  problem.
- Keep the final SQLite snapshot read-only for the approved archival period.
- Never automatically redirect reads or writes to SQLite.
- If an offline read-only view is later requested, design it separately,
  label it clearly, and prohibit all mutations.
- Remove SQLite runtime support only through a later explicit decision.
- Archive this plan only after architecture, migration, testing, and operations
  documents describe the final system.

## Verification matrix

### Structural parity

- Table and index inventory
- Primary and unique keys
- Foreign-key targets and delete behavior
- Check constraints and triggers
- Sequence values
- Schema migration versions
- Private-schema grants and ownership
- Exact `clearspend_app` grants created by each migration
- Denied table, sequence, and function access for API roles and `PUBLIC`

### Data parity

- Count and canonical hash per table
- Import and income audit status counts
- Exact, semantic, and transaction duplicate links
- Coverage relationships
- Mapping, display identity, override, reimbursement, event, recurring, and
  observation-review identity
- Reviewed questionable-field transformations or exclusions

### Financial and API parity

- Month, latest-year, and all-time dashboard payloads
- Combined and per-card scope
- Purchase activity versus billing-month reporting
- Categories and routine-only scope
- Personal spending after reimbursements
- Income, averages, and amount left
- Complete-history transaction search
- Event totals and grouping
- Recurring series, installments, lifecycle, and burden
- Qualifying, suppressed, grouped, reviewed, and future-period observations

### Write behavior

- Observation review and undo
- Category override
- Reimbursement add, update, and removal
- Event create, update, assignment, and unassignment
- Recurring verdict, alias scope, cadence, and lifecycle
- Merchant category and display-identity decisions
- Income import and duplicate handling
- Statement import, three duplicate layers, coverage, backup, and rollback

### Pre-cutover failure behavior

- Invalid credentials
- Missing or invalid CA certificate
- Basic remote unavailability
- PostgreSQL constraint rejection
- Failed import or migration rollback
- Backup creation, restore, or verification failure
- Clear error presentation without SQLite fallback

Credential rotation, provider-pausing simulations, and connection interruptions
move to Stage 7 operational hardening. Detailed pool and timeout controls are
added only in response to a demonstrated need.

## Performance comparison

Compare SQLite and PostgreSQL on the representative workflows:

- Dashboard load
- Changing month or card
- Transaction search
- Financial observations
- Import preview
- Approved import

Record the timings, require completion without timeouts or database errors, and
confirm normal use remains comfortable. Remote PostgreSQL may be slower than
local SQLite. Add indexes or consolidate queries only when an observed slowdown
justifies the change. Financial correctness is never traded for a faster
result.

## Security requirements

- Load the runtime database credential from macOS Keychain or another approved
  local secret mechanism.
- If the backend is hosted in a future project, replace Keychain with that
  hosting provider's secret manager.
- Never place connection strings, passwords, certificates, API keys, or
  service-role keys in Git, Vue, `dist/`, documentation examples, logs, health
  responses, URLs, or shell history.
- Use PostgreSQL database credentials for the Python connection, not a
  browser-oriented Supabase API key.
- Redact connection details from exceptions and diagnostics.
- Support credential rotation without schema changes.
- Give the running application only the least-privilege `clearspend_app`
  credential; reserve the separately stored Supabase `postgres` credential for
  explicit migrations, provisioning, and recovery.
- Require SSL enforcement and `sslmode=verify-full`.
- Apply network restrictions when the source network can be allowlisted
  reliably.
- Keep the `clearspend` schema outside the Data API exposed-schema list.
- Enable multi-factor authentication on the provider account.
- Maintain independent encrypted backups outside the live Supabase project.
- Treat dumps, parity reports, rehearsal copies, and recovery artifacts as
  private financial data.

## Backup and recovery requirements

SQLite's backup API cannot protect PostgreSQL. Before cutover, define and test:

- A verified logical or provider-supported PostgreSQL recovery artifact before
  schema migrations and approved imports
- Encryption and secure destination
- Retention and pruning policy
- Restore into an isolated database
- Schema-version verification after restore
- Count, relationship, total, and representative-decision verification

The free hosted database must never be the only recoverable copy.

## Testing and CI

- Keep the existing SQLite synthetic suite.
- Add PostgreSQL-backed synthetic coverage for every database query and service.
- Use a disposable PostgreSQL CI service, never the private Supabase project.
- Keep parser and pure-rule tests independent of either database.
- Add backend contract tests for sessions, transactions, rows, integrity
  errors, timeouts, and migration behavior.
- For every PostgreSQL schema migration, verify its explicit grants: newly
  created objects have exactly the required `clearspend_app` access,
  `clearspend_app` still has no ownership or schema-changing privileges, API
  roles remain denied, and non-public functions are not executable by `PUBLIC`.
- Run identical fixtures through both engines and compare normalized API
  payloads.
- Before cutover, test permissions, TLS failure, basic remote unavailability,
  and a clear busy response when the small pool cannot provide a connection.
  Run credential-rotation, provider-pausing, and connection-interruption
  exercises during Stage 7 hardening.
- Keep Playwright isolated from the archival SQLite snapshot and live Supabase
  database.

## Documentation ownership during implementation

Update the owning document in the same change that alters its contract:

- `ARCHITECTURE.md` for session boundaries, backend selection, pooling, and
  authority
- `DATABASE_MIGRATIONS.md` for PostgreSQL migrations and schema verification
- `OPERATIONS_AND_RECOVERY.md` for credentials, startup, backups, restore, and
  rollback
- `TESTING.md` for the backend matrix and PostgreSQL CI service
- `API_CONTRACTS.md` only if exchanged HTTP semantics change
- Domain documents only if financial behavior changes, which this migration is
  intended to avoid

No stage may treat test success as permission to copy private data or switch
database authority. Private rehearsal, production copy, and final cutover each
require explicit approval when performed.
