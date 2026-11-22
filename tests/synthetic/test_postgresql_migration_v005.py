from __future__ import annotations

import unittest

from clearspend.database.postgresql_migrations import v005_numeric_financial_values


class Result:
    def __init__(self, rows):
        self.rows = list(rows)

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows


class SyntheticCatalogConnection:
    def __init__(self) -> None:
        self.executed = []
        self.incorrect_column = None

    def execute(self, sql, parameters=None):
        self.executed.append((sql, parameters))
        if parameters is None and sql.lstrip().startswith("ALTER TABLE"):
            return Result([])
        if "information_schema.columns" in sql:
            table, columns = parameters
            return Result([
                {
                    "column_name": column,
                    "data_type": (
                        "text" if (table, column) == self.incorrect_column else "numeric"
                    ),
                }
                for column in columns
            ])
        if "grantee='clearspend_app'" in sql:
            return Result([
                {"privilege_type": privilege}
                for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE")
            ])
        if "information_schema.table_privileges" in sql:
            return Result([])
        if "pg_catalog.pg_tables" in sql:
            return Result([{"tableowner": "postgres"}])
        raise AssertionError(f"Unexpected verification SQL: {sql}")


class PostgreSQLMigrationV005Tests(unittest.TestCase):
    def test_apply_converts_every_financial_column_without_fixed_scale(self) -> None:
        connection = SyntheticCatalogConnection()

        v005_numeric_financial_values.apply(connection)

        combined = "\n".join(sql for sql, _ in connection.executed)
        self.assertEqual(len(connection.executed), 7)
        self.assertIn("ALTER COLUMN charged_amount TYPE NUMERIC", combined)
        self.assertIn("ALTER COLUMN exchange_rate TYPE NUMERIC", combined)
        self.assertIn("ALTER COLUMN budget TYPE NUMERIC", combined)
        self.assertIn("NULLIF(BTRIM(charged_amount), '')::NUMERIC", combined)
        self.assertNotIn("NUMERIC(", combined)

    def test_verify_accepts_numeric_types_and_preserved_security(self) -> None:
        self.assertEqual(
            v005_numeric_financial_values.verify(SyntheticCatalogConnection()),
            [],
        )

    def test_verify_reports_a_column_that_remains_text(self) -> None:
        connection = SyntheticCatalogConnection()
        connection.incorrect_column = ("transactions", "exchange_rate")

        self.assertIn(
            "Incorrect type: clearspend.transactions.exchange_rate must be numeric",
            v005_numeric_financial_values.verify(connection),
        )


if __name__ == "__main__":
    unittest.main()
