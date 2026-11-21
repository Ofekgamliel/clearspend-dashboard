# PostgreSQL cutover runbook

## Implementation status

The explicitly approved cutover completed on 2026-11-21. Every pre-resume gate
passed, the local server is running against PostgreSQL on its normal port, and
PostgreSQL is authoritative. The final SQLite source and verified backup are
archival snapshots. The first encrypted post-cutover PostgreSQL archive was
verified and its private off-device upload was confirmed. Ongoing work follows
the stabilization section of this runbook.

## Purpose and authority boundary

Use this runbook only for the explicitly approved transition from the local
SQLite database to the private Supabase PostgreSQL schema. The Python server is
stopped for the complete maintenance window. There is no temporary dual-write
or application read-only mode.

Before normal use resumes, any failed PostgreSQL gate returns the application
to the untouched SQLite snapshot. After normal PostgreSQL use resumes,
PostgreSQL is authoritative and recovery uses PostgreSQL backups; SQLite is an
archival snapshot and is not a rollback target.

The cutover itself requires explicit user approval. A rehearsal or successful
verification does not grant that approval.

## Private worksheet

Record these values outside Git before starting:

- Maintenance start and operator
- SQLite database path
- SQLite runtime/start command
- PostgreSQL runtime configuration path
- Approved Supabase project and region
- Expected schema version
- Latest verified SQLite fingerprint
- Latest PostgreSQL parity snapshot hash
- Final SQLite backup path, size, and verification result
- Final encrypted PostgreSQL archive path, size, checksum, and off-device copy
- Continue-or-return decision and time
- Maintenance completion time

Never place passwords, Keychain values, connection URIs, project references,
private local paths, or recovery-key material in this tracked runbook.

## 1. Pre-maintenance checks

1. Confirm the current branch and uncommitted migration work are the intended
   build.
2. Run the complete synthetic suite and require a pass.
3. Run `git diff --check`.
4. Confirm the PostgreSQL runtime configuration is ignored by Git and mode
   `0600`.
5. Confirm the certificate exists and the backup directory is mode `0700`.
6. Confirm the database and archive credentials are available from Keychain
   without printing them.
7. Confirm the independent archive key has a recoverable password-manager copy.
8. Confirm the latest populated encrypted archive exists off-device.
9. Confirm no staged import is open and no category, reimbursement, event,
   recurring, observation-review, or import write is in progress.
10. Record the approved source and target identifiers in the private worksheet.

Stop if any pre-maintenance check fails.

## 2. Enter maintenance

1. Stop the Python server completely.
2. Verify the normal dashboard port and any temporary test port have no
   listener.
3. Verify no ClearSpend server process remains.
4. Do not start either runtime again until the continue-or-return decision.

## 3. Protect and fingerprint SQLite

1. Open SQLite consistently and read-only for inspection.
2. Require `PRAGMA integrity_check` to return `ok`.
3. Require `PRAGMA foreign_key_check` to return no row.
4. Create a timestamped SQLite backup using the SQLite online-backup API.
5. Set the backup to mode `0600`.
6. Verify the backup integrity and logical table counts against the source.
7. Record the source size, modification time, SHA-256 fingerprint, schema
   status, table count, and total row count in the private worksheet.

Keep the source and final backup untouched for the rest of maintenance.

## 4. Establish the final PostgreSQL state

The preloaded Frankfurt rehearsal target may be reused only when all of these
are true:

- The SQLite fingerprint is unchanged from the verified private copy.
- The Python server has remained stopped.
- The target still reports the expected schema version.
- The deterministic content hash and all 802 presentation comparisons pass.

If any condition is false, do not append or overwrite individual rows. With
separate explicit approval, prepare an empty private schema, apply every
migration, copy all tables atomically from the protected SQLite source, advance
identity sequences, and verify the copy. A failed copy must roll back the
entire destination transaction.

For either path, require:

- Private schema ownership by the administrative role
- Restricted `clearspend_app` attributes and search path
- Explicit table, sequence, and function privileges from migrations 1--4
- No private-schema access for `PUBLIC`, `anon`, `authenticated`, or
  `service_role`
- TLS `verify-full` through the approved Session Pooler endpoint
- 15 application data tables and the expected total row count
- Exact relationship, content-hash, minimization, and identity-sequence checks
- All 802 financial/API/presentation comparisons
- Unchanged SQLite source fingerprint after verification

## 5. Final PostgreSQL recovery point

1. Create an encrypted logical archive of the populated final target.
2. Require the dump, encryption, complete in-memory decryption, and required
   table inventory checks to pass.
3. Confirm mode `0600`, nonzero size, and SHA-256 checksum.
4. Confirm no `.partial` artifact remains.
5. Upload the encrypted archive to the approved private off-device location.
6. Confirm the remote filename and size against the local artifact.
7. Record the archive evidence in the private worksheet.

Do not proceed without the verified local and off-device recovery points.

## 6. Performance and server smoke

1. Run the representative SQLite/PostgreSQL workflow benchmark.
2. Require comfortable completion without timeouts or database errors for:
   dashboard load, month change, card change, complete-history search,
   observations, import preview, and approved import.
3. Start the Python server on a temporary port with the PostgreSQL runtime
   configuration.
4. Require HTTP 200 and valid response shapes from health, dashboard,
   transactions, and observations.
5. Require the built dashboard shell to load.
6. Stop the temporary server and confirm the port is inactive.

## 7. Reversible write smoke

Use only the reviewed synthetic import rehearsal:

1. Preview one synthetic XLSX through the real staging path.
2. Confirm preview performs no database write.
3. Approve the synthetic import through the real PostgreSQL import boundary.
4. Require the advisory lock and encrypted pre-import backup before persistence.
5. Verify exactly one synthetic transaction is committed.
6. Remove the synthetic import, linkage, coverage, transaction, and dependent
   rows in one cleanup transaction.
7. Require all 15 table counts to return to baseline.
8. Rerun all 802 comparisons and require the original snapshot hash.
9. Confirm SQLite remained unchanged.

Stop and return to SQLite if cleanup or parity fails.

## 8. Start the intended PostgreSQL runtime

1. Start the local Python server on the normal dashboard port using only the
   approved PostgreSQL runtime configuration.
2. Do not provide the SQLite database argument and do not configure fallback.
3. Require startup schema verification before the port binds.
4. Run health and the same read-only smoke routes.
5. Load the dashboard and verify month/card changes, transaction presentation,
   calculations, observations, and import preview.
6. Keep the SQLite source and its final backup untouched.

## 9. Continue-or-return decision

Before normal use resumes, make and record one explicit decision.

### Continue with PostgreSQL

Choose this only when every structural, security, backup, parity, performance,
server, and reversible-write gate passed. Explicitly end maintenance and resume
normal use. PostgreSQL becomes authoritative at that moment.

### Return to SQLite

If any gate failed or approval is withheld:

1. Stop the PostgreSQL-configured server.
2. Confirm the normal port is inactive.
3. Start the server with the untouched SQLite source.
4. Run SQLite health and read-only smoke checks.
5. Record the failed gate and keep PostgreSQL isolated for diagnosis.

Do not copy PostgreSQL activity back into SQLite.

## 10. Post-cutover stabilization

After PostgreSQL becomes authoritative:

1. Mark the final SQLite source and backup as archival read-only snapshots.
2. Use PostgreSQL encrypted backups for recovery.
3. Confirm the first post-cutover archive is uploaded off-device.
4. Monitor connection failures, acquisition timeouts, statement timeouts,
   import failures, and unexpected Supabase exposure.
5. Recheck representative workflows after material schema or query changes.
6. Test restore procedures periodically in an isolated empty target.
7. Keep every local and off-device encrypted archive until the retention policy
   is explicitly changed.

## Completion record

The cutover is complete only when the private worksheet records:

- Every gate passed
- PostgreSQL runtime health and smoke results
- Final local and off-device backup evidence
- Explicit continue decision
- Authority transition time
- SQLite archival status
- No unresolved partial files, synthetic rows, or temporary server processes
