from __future__ import annotations

import sqlite3
from pathlib import Path

from clearspend.import_engine import ImportDatabase


SYNTHETIC_NOW = "2030-01-15T10:00:00"


def create_database(path: Path) -> None:
    database = ImportDatabase(path)
    database.close()


def connect(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def add_import(connection: sqlite3.Connection, *, name: str = "synthetic.json") -> int:
    connection.execute(
        """INSERT INTO imports(
        original_name,source_path,byte_hash,source_format,provider,card_last4,status,
        parsed_rows,inserted_rows,imported_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
        (name, name, f"hash-{name}", "SYNTHETIC", "synthetic", "0001", "imported", 0, 0, SYNTHETIC_NOW),
    )
    return int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])


def add_transaction(
    connection: sqlite3.Connection,
    import_id: int,
    *,
    key: str,
    merchant: str,
    amount: float,
    category: str,
    transaction_date: str = "2030-01-10",
    billing_month: str = "2030-01",
    card_last4: str = "0001",
) -> int:
    normalized = merchant.casefold()
    connection.execute(
        """INSERT INTO transactions(
        transaction_key,base_key,occurrence,provider,card_last4,source_sheet,
        transaction_date,billing_month,billing_month_source,merchant_raw,
        merchant_normalized,charged_amount,charged_currency,user_category,
        first_import_id,created_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            key,
            f"base-{key}",
            1,
            "synthetic",
            card_last4,
            "invented-data",
            transaction_date,
            billing_month,
            "synthetic",
            merchant,
            normalized,
            f"{amount:.2f}",
            "ILS",
            category,
            import_id,
            SYNTHETIC_NOW,
        ),
    )
    return int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])


def add_income(
    connection: sqlite3.Connection,
    *,
    month: str,
    source_name: str,
    amount: float,
) -> int:
    connection.execute(
        """INSERT INTO income_imports(
        original_name,source_path,byte_hash,source_format,status,
        parsed_rows,inserted_rows,imported_at
        ) VALUES(?,?,?,?,?,?,?,?)""",
        (
            "synthetic-income.json",
            "synthetic-income.json",
            "synthetic-income-hash",
            "SYNTHETIC",
            "imported",
            1,
            1,
            SYNTHETIC_NOW,
        ),
    )
    income_import_id = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])
    connection.execute(
        """INSERT INTO income_entries(
        month,source_name,amount,entry_key,first_import_id,created_at
        ) VALUES(?,?,?,?,?,?)""",
        (
            month,
            source_name,
            f"{amount:.2f}",
            f"{month}:{source_name.casefold()}",
            income_import_id,
            SYNTHETIC_NOW,
        ),
    )
    return int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])
