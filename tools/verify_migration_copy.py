#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import tempfile
from pathlib import Path
from typing import Any

from clearspend.database.migration_runner import inspect_database, migrate_database
from clearspend.server import (
    categories_payload,
    dashboard_payload,
    events_payload,
    mapping_payload,
    merchants_payload,
    observation_reviews_payload,
    recurring_payload,
    transactions_payload,
)


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_only_connection(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)


def copy_database(source: Path, destination: Path) -> None:
    source_connection = read_only_connection(source)
    destination_connection = sqlite3.connect(destination)
    try:
        source_connection.backup(destination_connection)
    finally:
        destination_connection.close()
        source_connection.close()


def integrity_check(path: Path) -> str:
    connection = read_only_connection(path)
    try:
        return str(connection.execute("PRAGMA integrity_check").fetchone()[0])
    finally:
        connection.close()


def normalized_value(value: Any) -> Any:
    if isinstance(value, bytes):
        return {"bytes_sha256": hashlib.sha256(value).hexdigest()}
    return value


def table_snapshot(path: Path) -> tuple[dict[str, dict[str, Any]], int]:
    connection = read_only_connection(path)
    try:
        tables = [
            row[0]
            for row in connection.execute(
                """SELECT name FROM sqlite_master
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
                  AND name!='schema_migrations'
                ORDER BY name"""
            )
        ]
        snapshot: dict[str, dict[str, Any]] = {}
        total_rows = 0
        for table in tables:
            rows = [
                json.dumps(
                    [normalized_value(value) for value in row],
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                for row in connection.execute(f'SELECT * FROM "{table}"')
            ]
            rows.sort()
            total_rows += len(rows)
            digest = hashlib.sha256("\n".join(rows).encode("utf-8")).hexdigest()
            snapshot[table] = {"rows": len(rows), "digest": digest}
        return snapshot, total_rows
    finally:
        connection.close()


def payload_digest(payload: object) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def available_months(path: Path) -> list[str]:
    connection = read_only_connection(path)
    try:
        return [
            row[0]
            for row in connection.execute(
                """SELECT month FROM (
                SELECT DISTINCT COALESCE(
                  billing_month,substr(billing_date,1,7),substr(transaction_date,1,7)
                ) month
                FROM transactions
                WHERE transaction_date IS NOT NULL OR billing_month IS NOT NULL
                UNION SELECT DISTINCT month FROM income_entries
                ) WHERE month IS NOT NULL ORDER BY month"""
            )
        ]
    finally:
        connection.close()


def api_snapshot(path: Path) -> dict[str, str]:
    payloads: dict[str, object] = {
        "mapping": mapping_payload(path),
        "merchants": merchants_payload(path),
        "observation-reviews": observation_reviews_payload(path),
    }
    for period in ("year", "all"):
        payloads[f"dashboard:{period}"] = dashboard_payload(path, period, "all")
        payloads[f"transactions:{period}"] = transactions_payload(path, period, "all")
        payloads[f"categories:{period}:all"] = categories_payload(
            path, period, "all", event_scope="all"
        )
        payloads[f"categories:{period}:routine"] = categories_payload(
            path, period, "all", event_scope="routine"
        )
        payloads[f"recurring:{period}"] = recurring_payload(path, period, "all")
        payloads[f"events:{period}"] = events_payload(path, period, "all")
    for month in available_months(path):
        payloads[f"dashboard:month:{month}"] = dashboard_payload(
            path, "month", "all", month
        )
        payloads[f"transactions:month:{month}"] = transactions_payload(
            path, "month", "all", month=month
        )
        payloads[f"categories:month:{month}:all"] = categories_payload(
            path, "month", "all", month, "all"
        )
        payloads[f"categories:month:{month}:routine"] = categories_payload(
            path, "month", "all", month, "routine"
        )
        payloads[f"recurring:month:{month}"] = recurring_payload(
            path, "month", "all", month
        )
        payloads[f"events:month:{month}"] = events_payload(path, "month", "all", month)
    return {name: payload_digest(payload) for name, payload in payloads.items()}


def verify_copy(source: Path, workspace: Path) -> dict[str, Any]:
    if not source.is_file():
        raise FileNotFoundError(f"Database does not exist: {source}")
    workspace.mkdir(parents=True, exist_ok=True)
    source_before = (source.stat().st_size, source.stat().st_mtime_ns, file_digest(source))
    copy_path = workspace / "migration-verification.db"
    copy_database(source, copy_path)
    if integrity_check(copy_path) != "ok":
        raise RuntimeError("Temporary database copy failed its integrity check")

    before_tables, total_rows = table_snapshot(copy_path)
    before_api = api_snapshot(copy_path)
    result = migrate_database(copy_path, workspace / "migration-backups")
    after_tables, after_total_rows = table_snapshot(copy_path)
    after_api = api_snapshot(copy_path)

    if before_tables != after_tables or total_rows != after_total_rows:
        raise RuntimeError("Existing table contents changed during baseline registration")
    if before_api != after_api:
        changed = sorted(set(before_api) | set(after_api))
        changed = [name for name in changed if before_api.get(name) != after_api.get(name)]
        raise RuntimeError(f"API payload changed after migration: {', '.join(changed)}")
    if inspect_database(copy_path).state != "versioned":
        raise RuntimeError("Migrated copy did not report a versioned schema")
    if result.backup_path is None or integrity_check(result.backup_path) != "ok":
        raise RuntimeError("Migration backup was not created and verified")
    backup_tables, backup_total_rows = table_snapshot(result.backup_path)
    if backup_tables != before_tables or backup_total_rows != total_rows:
        raise RuntimeError("Migration backup does not match the pre-migration copy")

    source_after = (source.stat().st_size, source.stat().st_mtime_ns, file_digest(source))
    if source_before != source_after:
        raise RuntimeError("Source database changed during copy verification")
    source_connection = read_only_connection(source)
    try:
        source_version_table = int(
            source_connection.execute(
                """SELECT COUNT(*) FROM sqlite_master
                WHERE type='table' AND name='schema_migrations'"""
            ).fetchone()[0]
        )
    finally:
        source_connection.close()
    if source_version_table:
        raise RuntimeError("Source database was unexpectedly versioned")

    return {
        "status": "verified",
        "tables_compared": len(before_tables),
        "rows_compared": total_rows,
        "api_payloads_compared": len(before_api),
        "source_unchanged": True,
        "copy_version": result.ending_version,
        "migration_backup_verified": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify ClearSpend schema migration against a temporary database copy."
    )
    parser.add_argument("database", type=Path)
    parser.add_argument(
        "--workspace",
        type=Path,
        help="Temporary output directory. A temporary directory is used when omitted.",
    )
    args = parser.parse_args()

    if args.workspace:
        result = verify_copy(args.database, args.workspace)
    else:
        with tempfile.TemporaryDirectory(prefix="clearspend-migration-verification-") as directory:
            result = verify_copy(args.database, Path(directory))
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
