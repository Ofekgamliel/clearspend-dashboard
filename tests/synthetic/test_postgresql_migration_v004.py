from __future__ import annotations

import unittest

from clearspend.database.postgresql_migrations import v004_import_linkage


class Result:
    def __init__(self, rows):
        self.rows = list(rows)

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows


class SyntheticCatalogConnection:
    def __init__(self) -> None:
        self.present = True
        self.executed = []

    def execute(self, sql, parameters=None):
        self.executed.append((sql, parameters))
        if parameters is None and sql.lstrip().startswith(("CREATE", "GRANT", "REVOKE")):
            return Result([])
        if "to_regclass" in sql:
            return Result([{"present": self.present}])
        if "information_schema.columns" in sql:
            return Result([
                {"column_name": column}
                for column in v004_import_linkage.TABLE_COLUMNS["import_transactions"]
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


class PostgreSQLMigrationV004Tests(unittest.TestCase):
    def test_apply_creates_private_import_linkage(self) -> None:
        connection = SyntheticCatalogConnection()
        v004_import_linkage.apply(connection)
        combined = "\n".join(sql for sql, _ in connection.executed)
        self.assertIn("CREATE TABLE clearspend.import_transactions", combined)
        self.assertIn("PRIMARY KEY(import_id,transaction_id)", combined)
        self.assertIn("GRANT SELECT, INSERT, UPDATE, DELETE", combined)
        self.assertNotIn("ALTER DEFAULT PRIVILEGES", combined)

    def test_verify_accepts_complete_private_table(self) -> None:
        self.assertEqual(v004_import_linkage.verify(SyntheticCatalogConnection()), [])

    def test_verify_reports_missing_table(self) -> None:
        connection = SyntheticCatalogConnection()
        connection.present = False
        self.assertEqual(
            v004_import_linkage.verify(connection),
            ["Missing table: clearspend.import_transactions"],
        )


if __name__ == "__main__":
    unittest.main()
