#!/usr/bin/env python3
"""Compare private SQLite presentation with PostgreSQL without printing data."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from clearspend.database.postgresql import PostgreSQLPool
from clearspend.database.postgresql_parity import verify_financial_parity
from clearspend.database.runtime_config import load_postgresql_runtime_configuration


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Compare SQLite and PostgreSQL dashboard calculations and "
            "transaction presentation without printing financial values."
        )
    )
    parser.add_argument("sqlite_database", type=Path)
    parser.add_argument("--postgresql-config", required=True, type=Path)
    args = parser.parse_args()

    sqlite_database = args.sqlite_database.resolve()
    if not sqlite_database.is_file():
        parser.error("SQLite database does not exist")
    source_before = (
        sqlite_database.stat().st_size,
        sqlite_database.stat().st_mtime_ns,
        _file_digest(sqlite_database),
    )
    configuration = load_postgresql_runtime_configuration(
        args.postgresql_config.resolve()
    )
    pool = PostgreSQLPool(configuration.database)
    pool.open()
    try:
        report = verify_financial_parity(sqlite_database, pool)
    finally:
        pool.close()
    source_after = (
        sqlite_database.stat().st_size,
        sqlite_database.stat().st_mtime_ns,
        _file_digest(sqlite_database),
    )
    if source_before != source_after:
        raise RuntimeError("SQLite source changed during parity verification")
    print(json.dumps({
        "status": "verified",
        "comparisons": report.comparisons,
        "snapshot_sha256": report.snapshot_sha256,
        "sqlite_source_unchanged": True,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
