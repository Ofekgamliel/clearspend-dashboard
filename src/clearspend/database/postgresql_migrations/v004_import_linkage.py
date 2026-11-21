from __future__ import annotations

from typing import Any


VERSION = 4
NAME = "import_linkage"

TABLE_COLUMNS = {
    "import_transactions": {"import_id", "transaction_id", "was_duplicate"},
}

CREATE_STATEMENTS = (
    """CREATE TABLE clearspend.import_transactions (
      import_id BIGINT NOT NULL REFERENCES clearspend.imports(id),
      transaction_id BIGINT NOT NULL REFERENCES clearspend.transactions(id),
      was_duplicate INTEGER NOT NULL CHECK(was_duplicate IN (0,1)),
      PRIMARY KEY(import_id,transaction_id)
    )""",
)

PRIVILEGE_STATEMENTS = (
    """REVOKE ALL PRIVILEGES ON TABLE clearspend.import_transactions
    FROM PUBLIC, anon, authenticated, service_role""",
    """GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE
    clearspend.import_transactions TO clearspend_app""",
)


def apply(connection: Any) -> None:
    for statement in CREATE_STATEMENTS + PRIVILEGE_STATEMENTS:
        connection.execute(statement)


def verify(connection: Any) -> list[str]:
    problems: list[str] = []
    row = connection.execute(
        "SELECT to_regclass(?) IS NOT NULL AS present",
        ("clearspend.import_transactions",),
    ).fetchone()
    if not row["present"]:
        return ["Missing table: clearspend.import_transactions"]
    columns = connection.execute(
        """SELECT column_name FROM information_schema.columns
        WHERE table_schema='clearspend' AND table_name='import_transactions'"""
    ).fetchall()
    actual = {column["column_name"] for column in columns}
    for column in sorted(TABLE_COLUMNS["import_transactions"] - actual):
        problems.append(f"Missing column: clearspend.import_transactions.{column}")
    privileges = {
        item["privilege_type"]
        for item in connection.execute(
            """SELECT privilege_type FROM information_schema.table_privileges
            WHERE table_schema='clearspend' AND table_name='import_transactions'
            AND grantee='clearspend_app'"""
        ).fetchall()
    }
    if privileges != {"SELECT", "INSERT", "UPDATE", "DELETE"}:
        problems.append("Incorrect clearspend_app privileges: clearspend.import_transactions")
    unexpected = connection.execute(
        """SELECT grantee,privilege_type FROM information_schema.table_privileges
        WHERE table_schema='clearspend' AND table_name='import_transactions'
        AND grantee IN ('PUBLIC','anon','authenticated','service_role')"""
    ).fetchall()
    if unexpected:
        problems.append("API roles or PUBLIC can access import_transactions")
    owner = connection.execute(
        """SELECT tableowner FROM pg_catalog.pg_tables
        WHERE schemaname='clearspend' AND tablename='import_transactions'"""
    ).fetchone()
    if owner and owner["tableowner"] == "clearspend_app":
        problems.append("clearspend_app owns import_transactions")
    return problems
