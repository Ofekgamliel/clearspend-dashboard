from __future__ import annotations

from typing import Any


VERSION = 5
NAME = "numeric_financial_values"

NUMERIC_COLUMNS = {
    "transactions": ("charged_amount", "original_amount", "exchange_rate"),
    "transaction_spending_adjustments": ("reimbursed_amount",),
    "income_entries": ("amount",),
    "events": ("budget",),
    "import_coverage": ("official_total",),
}

ALTER_STATEMENTS = tuple(
    f"""ALTER TABLE clearspend.{table}
    ALTER COLUMN {column} TYPE NUMERIC
    USING NULLIF(BTRIM({column}), '')::NUMERIC"""
    for table, columns in NUMERIC_COLUMNS.items()
    for column in columns
)


def apply(connection: Any) -> None:
    for statement in ALTER_STATEMENTS:
        connection.execute(statement)


def verify(connection: Any) -> list[str]:
    problems: list[str] = []
    for table, columns in NUMERIC_COLUMNS.items():
        rows = connection.execute(
            """SELECT column_name,data_type FROM information_schema.columns
            WHERE table_schema='clearspend' AND table_name=?
            AND column_name = ANY(?)""",
            (table, list(columns)),
        ).fetchall()
        actual = {
            str(row["column_name"]): str(row["data_type"])
            for row in rows
        }
        for column in columns:
            if actual.get(column) != "numeric":
                problems.append(
                    f"Incorrect type: clearspend.{table}.{column} must be numeric"
                )

        privileges = {
            row["privilege_type"]
            for row in connection.execute(
                """SELECT privilege_type FROM information_schema.table_privileges
                WHERE table_schema='clearspend' AND table_name=?
                AND grantee='clearspend_app'""",
                (table,),
            ).fetchall()
        }
        if privileges != {"SELECT", "INSERT", "UPDATE", "DELETE"}:
            problems.append(f"Incorrect clearspend_app privileges: clearspend.{table}")

        unexpected = connection.execute(
            """SELECT grantee,privilege_type FROM information_schema.table_privileges
            WHERE table_schema='clearspend' AND table_name=?
            AND grantee IN ('PUBLIC','anon','authenticated','service_role')""",
            (table,),
        ).fetchall()
        if unexpected:
            problems.append(f"API roles or PUBLIC can access {table}")

        owner = connection.execute(
            """SELECT tableowner FROM pg_catalog.pg_tables
            WHERE schemaname='clearspend' AND tablename=?""",
            (table,),
        ).fetchone()
        if owner and owner["tableowner"] == "clearspend_app":
            problems.append(f"clearspend_app owns {table}")
    return problems
