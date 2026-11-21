from __future__ import annotations

import unittest

from clearspend.database.postgresql_migrations import v003_merchant_management


class Result:
    def __init__(self, rows):
        self.rows = list(rows)

    def fetchone(self):
        return self.rows[0] if self.rows else None

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
            return Result([
                {"column_name": column}
                for column in v003_merchant_management.TABLE_COLUMNS[parameters[0]]
            ])
        if "grantee='clearspend_app'" in sql:
            return Result([
                {"privilege_type": privilege}
                for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE")
            ])
        if "pg_catalog.pg_trigger" in sql:
            return Result([{"present": True}])
        if "pg_catalog.pg_proc" in sql:
            return Result([{
                "owner": "postgres",
                "runtime_execute": False,
                "anon_execute": False,
                "authenticated_execute": False,
                "service_execute": False,
            }])
        if "information_schema.table_privileges" in sql:
            return Result([])
        if "pg_catalog.pg_tables" in sql:
            return Result([])
        raise AssertionError(f"Unexpected verification SQL: {sql}")


class PostgreSQLMigrationV003Tests(unittest.TestCase):
    def test_apply_creates_private_mapping_dependencies_and_trigger(self) -> None:
        connection = SyntheticCatalogConnection()

        v003_merchant_management.apply(connection)

        combined = "\n".join(sql for sql, _ in connection.executed)
        self.assertIn("merchant_mappings", combined)
        self.assertIn("import_coverage", combined)
        self.assertIn("recurring_profiles", combined)
        self.assertIn("BEFORE INSERT", combined)
        self.assertIn("IF FOUND", combined)
        self.assertIn("SET search_path = pg_catalog", combined)
        self.assertIn("REVOKE ALL PRIVILEGES ON FUNCTION", combined)
        self.assertNotIn("ALTER DEFAULT PRIVILEGES", combined)

    def test_verify_accepts_complete_private_schema_slice(self) -> None:
        self.assertEqual(v003_merchant_management.verify(SyntheticCatalogConnection()), [])

    def test_verify_reports_missing_table_index_and_trigger(self) -> None:
        connection = SyntheticCatalogConnection()
        connection.missing_objects = {
            "clearspend.merchant_mappings",
            "clearspend.idx_recurring_members_merchant",
        }
        original_execute = connection.execute

        def execute(sql, parameters=None):
            if "pg_catalog.pg_trigger" in sql:
                connection.executed.append((sql, parameters))
                return Result([{"present": False}])
            return original_execute(sql, parameters)

        connection.execute = execute
        problems = v003_merchant_management.verify(connection)

        self.assertIn("Missing table: clearspend.merchant_mappings", problems)
        self.assertIn("Missing index: clearspend.idx_recurring_members_merchant", problems)
        self.assertIn("Missing merchant-mapping transaction trigger", problems)


if __name__ == "__main__":
    unittest.main()
