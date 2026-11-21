from __future__ import annotations

import unittest

from clearspend.database.postgresql_migrations import v002_transaction_browsing


class Result:
    def __init__(self, rows):
        self.rows = list(rows)

    def fetchone(self):
        return self.rows[0]

    def fetchall(self):
        return self.rows


class SyntheticCatalogConnection:
    def __init__(self) -> None:
        self.missing_objects: set[str] = set()
        self.executed: list[tuple[str, object]] = []

    def execute(self, sql, parameters=None):
        self.executed.append((sql, parameters))
        if parameters is None and sql.lstrip().startswith(("CREATE", "GRANT", "REVOKE")):
            return Result([])
        if "to_regclass" in sql:
            return Result([{"present": parameters[0] not in self.missing_objects}])
        if "information_schema.columns" in sql:
            table = parameters[0]
            return Result(
                [
                    {"column_name": column}
                    for column in v002_transaction_browsing.TABLE_COLUMNS[table]
                ]
            )
        if "grantee='clearspend_app'" in sql:
            return Result(
                [
                    {"privilege_type": privilege}
                    for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE")
                ]
            )
        if "has_sequence_privilege" in sql:
            return Result([{"runtime_allowed": True}])
        if "information_schema.table_privileges" in sql:
            return Result([])
        if "information_schema.usage_privileges" in sql:
            return Result([])
        if "pg_catalog.pg_tables" in sql:
            return Result([])
        raise AssertionError(f"Unexpected verification SQL: {sql}")


class PostgreSQLMigrationV002Tests(unittest.TestCase):
    def test_apply_creates_transaction_dependencies_and_exact_grants(self) -> None:
        connection = SyntheticCatalogConnection()

        v002_transaction_browsing.apply(connection)

        statements = [sql for sql, _ in connection.executed]
        combined = "\n".join(statements)
        self.assertIn("transaction_category_overrides", combined)
        self.assertIn("transaction_spending_adjustments", combined)
        self.assertIn("merchant_display_mappings", combined)
        self.assertIn("income_entries", combined)
        self.assertIn("event_transactions", combined)
        self.assertIn("ON DELETE CASCADE", combined)
        self.assertIn("GRANT SELECT, INSERT, UPDATE, DELETE", combined)
        self.assertIn("GRANT USAGE, SELECT ON SEQUENCE", combined)
        self.assertNotIn("ALTER DEFAULT PRIVILEGES", combined)

    def test_verify_accepts_complete_private_schema_slice(self) -> None:
        connection = SyntheticCatalogConnection()

        self.assertEqual(v002_transaction_browsing.verify(connection), [])

    def test_verify_reports_missing_table_and_index(self) -> None:
        connection = SyntheticCatalogConnection()
        connection.missing_objects = {
            "clearspend.transaction_spending_adjustments",
            "clearspend.idx_income_entries_month",
        }

        problems = v002_transaction_browsing.verify(connection)

        self.assertIn(
            "Missing table: clearspend.transaction_spending_adjustments",
            problems,
        )
        self.assertIn("Missing index: clearspend.idx_income_entries_month", problems)


if __name__ == "__main__":
    unittest.main()
