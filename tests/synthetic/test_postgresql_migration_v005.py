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
        if parameters is None and (
            sql.lstrip().startswith("ALTER TABLE")
            or sql.lstrip().startswith("UPDATE clearspend.transactions")
        ):
            return Result([])
        if "column_name='exchange_rate_source_text'" in sql:
            return Result([{"data_type": "text"}])
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
        self.assertEqual(len(connection.executed), 9)
        self.assertIn("ADD COLUMN exchange_rate_source_text TEXT", combined)
        self.assertIn("SET exchange_rate_source_text = exchange_rate", combined)
        self.assertIn("ALTER COLUMN charged_amount TYPE NUMERIC", combined)
        self.assertIn("ALTER COLUMN exchange_rate TYPE NUMERIC", combined)
        self.assertIn("ALTER COLUMN budget TYPE NUMERIC", combined)
        self.assertIn("NULLIF(BTRIM(charged_amount), '')::NUMERIC", combined)
        self.assertIn(
            "pg_input_is_valid(NULLIF(BTRIM(exchange_rate), ''), 'numeric')",
            combined,
        )
        self.assertIn(
            "THEN NULLIF(BTRIM(exchange_rate), '')::NUMERIC ELSE NULL END",
            combined,
        )
        self.assertNotIn("NUMERIC(", combined)

    def test_only_exchange_rate_tolerates_preserved_provider_labels(self) -> None:
        statements = "\n".join(v005_numeric_financial_values.ALTER_STATEMENTS)

        self.assertEqual(statements.count("pg_input_is_valid"), 1)
        self.assertEqual(statements.count("ELSE NULL END"), 1)

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
