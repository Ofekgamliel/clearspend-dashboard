from __future__ import annotations

import sqlite3

from clearspend.database.schema import (
    BASE_SCHEMA_SQL,
    BILLING_MONTH_INDEX_SQL,
    MERCHANT_MAPPING_TRIGGER_SQL,
)


VERSION = 1
NAME = "current_baseline"


def _execute_script(connection: sqlite3.Connection, script: str) -> None:
    statement = ""
    for line in script.splitlines():
        statement = f"{statement}\n{line}".strip()
        if not sqlite3.complete_statement(statement):
            continue
        if not statement.upper().startswith("PRAGMA FOREIGN_KEYS"):
            connection.execute(statement)
        statement = ""
    if statement.strip():
        raise ValueError("Incomplete SQL in the current baseline schema")


def apply(connection: sqlite3.Connection) -> None:
    _execute_script(connection, BASE_SCHEMA_SQL)
    connection.execute(BILLING_MONTH_INDEX_SQL)
    _execute_script(connection, MERCHANT_MAPPING_TRIGGER_SQL)


def _signature(connection: sqlite3.Connection) -> dict:
    tables = {
        row[0]
        for row in connection.execute(
            """SELECT name FROM sqlite_master
            WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name!='schema_migrations'"""
        )
    }
    columns = {
        table: {
            row[1]: (str(row[2]).upper(), int(row[3]), int(row[5]))
            for row in connection.execute(f'PRAGMA table_info("{table}")')
        }
        for table in tables
    }
    indexes = {
        row[0]
        for row in connection.execute(
            """SELECT name FROM sqlite_master
            WHERE type='index' AND name NOT LIKE 'sqlite_%'"""
        )
    }
    triggers = {
        row[0]
        for row in connection.execute("SELECT name FROM sqlite_master WHERE type='trigger'")
    }
    return {"tables": tables, "columns": columns, "indexes": indexes, "triggers": triggers}


def expected_signature() -> dict:
    connection = sqlite3.connect(":memory:")
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        apply(connection)
        return _signature(connection)
    finally:
        connection.close()


def verify(connection: sqlite3.Connection) -> list[str]:
    expected = expected_signature()
    actual = _signature(connection)
    problems: list[str] = []
    for table in sorted(expected["tables"] - actual["tables"]):
        problems.append(f"Missing table: {table}")
    for table in sorted(expected["tables"] & actual["tables"]):
        expected_columns = expected["columns"][table]
        actual_columns = actual["columns"][table]
        for column in sorted(expected_columns.keys() - actual_columns.keys()):
            problems.append(f"Missing column: {table}.{column}")
        for column in sorted(expected_columns.keys() & actual_columns.keys()):
            if expected_columns[column] != actual_columns[column]:
                problems.append(f"Incompatible column: {table}.{column}")
    for index in sorted(expected["indexes"] - actual["indexes"]):
        problems.append(f"Missing index: {index}")
    for trigger in sorted(expected["triggers"] - actual["triggers"]):
        problems.append(f"Missing trigger: {trigger}")
    return problems
