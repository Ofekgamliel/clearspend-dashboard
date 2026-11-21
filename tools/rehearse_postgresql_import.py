#!/usr/bin/env python3
"""Run and clean up one backed-up synthetic PostgreSQL import rehearsal."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
import time
from io import BytesIO
from pathlib import Path

from openpyxl import Workbook

from clearspend.database.connection import database_transaction
from clearspend.database.postgresql import PostgreSQLPool
from clearspend.database.postgresql_copy import TABLES
from clearspend.database.runtime_config import load_postgresql_runtime_configuration
from clearspend.http.imports import (
    cancel_staged_import,
    commit_staged_import,
    process_import_uploads,
)
from clearspend.http.multipart import UploadedFile


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _synthetic_statement(path: Path) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Synthetic Isracard"
    sheet["A1"] = "תאריך רכישה"
    sheet["C1"] = "December 2030"
    sheet["A2"] = "ישראכרט Synthetic - 0003"
    sheet["A3"] = "נכונים לתאריך 31/12/2030"
    sheet["B4"] = 'סה"כ לחיוב החודש בכרטיס'
    sheet["E4"] = "300.00"
    sheet["A5"] = "10.12.30"
    sheet["B5"] = "Synthetic PostgreSQL Rehearsal"
    sheet["C5"] = "300.00"
    sheet["D5"] = "ILS"
    sheet["E5"] = "300.00"
    sheet["F5"] = "ILS"
    sheet["G5"] = "clearspend-postgresql-rehearsal"
    workbook.save(path)


def _row_counts(pool: PostgreSQLPool) -> dict[str, int]:
    with pool.connection() as connection:
        return {
            table.name: int(connection.execute(
                f"SELECT COUNT(*) AS row_count FROM clearspend.{table.name}"
            ).fetchone()["row_count"])
            for table in TABLES
        }


def _cleanup_import(pool: PostgreSQLPool, import_id: int) -> None:
    with database_transaction(pool) as connection:
        connection.execute(
            "DELETE FROM clearspend.import_transactions WHERE import_id=?",
            (import_id,),
        )
        connection.execute(
            "DELETE FROM clearspend.transactions WHERE first_import_id=?",
            (import_id,),
        )
        connection.execute(
            "DELETE FROM clearspend.import_coverage WHERE import_id=?",
            (import_id,),
        )
        connection.execute(
            "DELETE FROM clearspend.imports WHERE id=?",
            (import_id,),
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("sqlite_database", type=Path)
    parser.add_argument("--postgresql-config", required=True, type=Path)
    args = parser.parse_args()

    sqlite_database = args.sqlite_database.resolve()
    sqlite_before = (sqlite_database.stat().st_size, _sha256(sqlite_database))
    configuration = load_postgresql_runtime_configuration(
        args.postgresql_config.resolve()
    )
    pool = PostgreSQLPool(configuration.database)
    pool.open()
    staged_imports: dict[str, dict] = {}
    batch_id = ""
    import_id = 0
    try:
        before_counts = _row_counts(pool)
        with tempfile.TemporaryDirectory() as directory:
            statement_path = Path(directory) / "synthetic-rehearsal.xlsx"
            _synthetic_statement(statement_path)
            preview_started = time.perf_counter()
            analysis, preview_status = process_import_uploads(
                pool,
                staged_imports,
                [UploadedFile(statement_path.name, BytesIO(statement_path.read_bytes()))],
                local_state_directory=configuration.local_state_directory,
            )
            preview_ms = round((time.perf_counter() - preview_started) * 1000, 1)
            if preview_status != 200:
                raise RuntimeError("Synthetic import preview failed")
            batch_id = str(analysis["batch_id"])
            decisions = [
                {
                    "merchant_normalized": item["merchant_normalized"],
                    "resolution": "needs_review",
                    "scope": "batch",
                    "category": "",
                }
                for item in analysis.get("merchants", ())
                if item.get("needs_review")
            ]
            duplicate_decisions = [
                {"candidate_id": item["candidate_id"], "action": "import"}
                for item in analysis.get("possible_duplicates", ())
            ]
            reconciled_files = [
                item["filename"] for item in analysis.get("files", ())
            ]
            commit_started = time.perf_counter()
            result, commit_status = commit_staged_import(
                pool,
                staged_imports,
                {
                    "batch_id": batch_id,
                    "decisions": decisions,
                    "duplicate_decisions": duplicate_decisions,
                    "reconciled_files": reconciled_files,
                },
                postgresql_backup=configuration.backup,
            )
            commit_ms = round((time.perf_counter() - commit_started) * 1000, 1)
            batch_id = ""
            if commit_status != 200 or result.get("status") != "committed":
                raise RuntimeError("Synthetic approved import failed")
            results = result.get("results") or ()
            if len(results) != 1 or int(results[0].get("inserted", 0)) != 1:
                raise RuntimeError("Synthetic approved import result was unexpected")
            import_id = int(results[0]["import_id"])
            archive = Path(str(result["backup"]))
            if not archive.is_file() or archive.stat().st_size == 0:
                raise RuntimeError("Synthetic approved import backup is missing")
            backup_name = archive.name
            backup_size = archive.stat().st_size

        _cleanup_import(pool, import_id)
        import_id = 0
        after_counts = _row_counts(pool)
        if after_counts != before_counts:
            raise RuntimeError("Synthetic import cleanup did not restore table counts")
    finally:
        if batch_id:
            cancel_staged_import(staged_imports, {"batch_id": batch_id})
        pool.close()

    sqlite_after = (sqlite_database.stat().st_size, _sha256(sqlite_database))
    print(json.dumps(
        {
            "status": "verified",
            "preview_ms": preview_ms,
            "approved_import_ms": commit_ms,
            "inserted_rows": 1,
            "cleanup_verified": True,
            "sqlite_source_unchanged": sqlite_before == sqlite_after,
            "backup": {"name": backup_name, "size": backup_size},
        },
        indent=2,
        sort_keys=True,
    ))


if __name__ == "__main__":
    main()
