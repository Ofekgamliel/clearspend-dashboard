from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Callable

from clearspend.database.backup import create_verified_backup
from clearspend.database.connection import connect_database
from clearspend.database.postgresql import PostgreSQLPool
from clearspend.database.postgresql_backup import (
    PostgreSQLBackupConfiguration,
    create_verified_postgresql_backup,
)
from clearspend.database.settings import DatabaseBackend
from clearspend.import_engine import ImportDatabase
from clearspend.staging.coverage import save_import_coverage
from clearspend.staging.decisions import (
    apply_imported_transaction_decisions,
    apply_permanent_merchant_decisions,
    merchant_decision_map,
    merchants_requiring_review,
    reviewed_duplicate_matches,
)


POSTGRESQL_IMPORT_LOCK_ID = 1_127_033_681


def _review_context(
    batch: dict,
    decisions: list[dict],
    duplicate_decisions: list[dict],
    analysis: dict,
) -> tuple[list[dict], dict[str, dict], set[str], dict[int, dict[str, int]]]:
    uploads = batch.get("uploads", [])
    if len(uploads) != 1:
        raise ValueError("Exactly one staged statement is required for import")
    decision_map = merchant_decision_map(decisions)
    review_required_merchants = merchants_requiring_review(analysis)
    reviewed_matches_by_file = reviewed_duplicate_matches(analysis, duplicate_decisions)
    return (
        uploads,
        decision_map,
        review_required_merchants,
        reviewed_matches_by_file,
    )


def _persist_reviewed_statement(
    connection,
    backend: DatabaseBackend,
    uploads: list[dict],
    decision_map: dict[str, dict],
    review_required_merchants: set[str],
    reviewed_matches_by_file: dict[int, dict[str, int]],
    analysis: dict,
) -> list[dict]:
    """Write one reviewed statement inside a caller-owned transaction."""
    db = ImportDatabase.from_connection(connection, backend)
    results: list[dict] = []
    now = datetime.now().astimezone().isoformat()
    apply_permanent_merchant_decisions(connection, decision_map, now)
    for file_index, staged_file in enumerate(uploads):
        pending_keys = {
            item["transaction_key"]
            for item in analysis.get("pending_transactions", [])
            if int(item["file_index"]) == file_index
        }
        result = db.import_file(
            staged_file["path"],
            probable_duplicate_matches=reviewed_matches_by_file.get(file_index),
            excluded_transaction_keys=pending_keys,
            original_name=staged_file["filename"],
            commit=False,
        )
        if result.get("status") == "failed":
            raise ValueError(
                result.get("error") or "The staged statement could not be imported"
            )
        if result.get("import_id"):
            table = "income_imports" if result.get("kind") == "income" else "imports"
            connection.execute(
                f"UPDATE {table} SET original_name=? WHERE id=?",
                (staged_file["filename"], result["import_id"]),
            )
            if result.get("kind") != "income":
                save_import_coverage(
                    connection,
                    result["import_id"],
                    analysis["files"][file_index].get("coverage", []),
                )
        excluded = 0
        if result.get("import_id") and result.get("kind") != "income":
            excluded = apply_imported_transaction_decisions(
                connection,
                result["import_id"],
                decision_map,
                review_required_merchants,
                now,
            )
            if excluded:
                connection.execute(
                    """UPDATE imports SET inserted_rows=CASE
                    WHEN inserted_rows>? THEN inserted_rows-? ELSE 0 END WHERE id=?""",
                    (excluded, excluded, result["import_id"]),
                )
                result["inserted"] = max(
                    int(result.get("inserted", 0)) - excluded,
                    0,
                )
                result["excluded"] = excluded
        result["filename"] = staged_file["filename"]
        results.append(result)
    return results


def persist_reviewed_statement_in_transaction(
    connection,
    backend: DatabaseBackend,
    batch: dict,
    decisions: list[dict],
    duplicate_decisions: list[dict],
    analysis: dict,
) -> list[dict]:
    """Persist reviewed import writes after the caller has secured a backup."""
    context = _review_context(batch, decisions, duplicate_decisions, analysis)
    return _persist_reviewed_statement(connection, backend, *context, analysis)


def commit_staged_statement(
    database: Path,
    batch: dict,
    decisions: list[dict],
    duplicate_decisions: list[dict],
    analysis: dict,
) -> dict:
    """Atomically commit one reviewed statement after a verified SQLite backup."""
    context = _review_context(batch, decisions, duplicate_decisions, analysis)
    db = ImportDatabase(database)
    try:
        db.connection.execute("BEGIN IMMEDIATE")
        backup_source = connect_database(database)
        try:
            backup_path = create_verified_backup(
                backup_source,
                database,
                database.parent / "backups",
                "before-import",
            )
        finally:
            backup_source.close()
        results = _persist_reviewed_statement(
            db.connection,
            DatabaseBackend.SQLITE,
            *context,
            analysis,
        )
        db.connection.commit()
        return {"status": "committed", "backup": str(backup_path), "results": results}
    except Exception:
        db.connection.rollback()
        raise
    finally:
        db.close()


def commit_staged_statement_postgresql(
    pool: PostgreSQLPool,
    backup: PostgreSQLBackupConfiguration,
    batch: dict,
    decisions: list[dict],
    duplicate_decisions: list[dict],
    analysis: dict,
    *,
    backup_creator: Callable | None = None,
) -> dict:
    """Back up and atomically commit one reviewed statement to PostgreSQL."""
    context = _review_context(batch, decisions, duplicate_decisions, analysis)
    create_backup = backup_creator or create_verified_postgresql_backup
    with pool.connection() as connection:
        try:
            connection.execute(
                "SELECT pg_advisory_xact_lock(?)",
                (POSTGRESQL_IMPORT_LOCK_ID,),
            )
            backup_path = create_backup(
                pool.settings,
                backup.directory,
                "before-import",
                encryption_keychain_service=backup.encryption_keychain_service,
                encryption_keychain_account=backup.encryption_keychain_account,
                pg_dump_path=backup.pg_dump_path,
                pg_restore_path=backup.pg_restore_path,
                openssl_path=backup.openssl_path,
            )
            results = _persist_reviewed_statement(
                connection,
                DatabaseBackend.POSTGRESQL,
                *context,
                analysis,
            )
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
    return {"status": "committed", "backup": str(backup_path), "results": results}
