from __future__ import annotations

import unittest
from contextlib import contextmanager
from types import ModuleType
from unittest.mock import Mock, patch

from clearspend.database.postgresql_migration_runner import (
    MIGRATION_TABLE_SQL,
    PostgreSQLMigrationError,
    inspect_postgresql_schema,
    migrate_postgresql,
)


def synthetic_migration(version: int, name: str = "synthetic_change") -> ModuleType:
    migration = ModuleType(f"synthetic_migration_{version}")
    migration.VERSION = version
    migration.NAME = name
    migration.apply = Mock()
    migration.verify = Mock(return_value=[])
    return migration


@contextmanager
def yielding(value):
    yield value


class PostgreSQLMigrationRunnerTests(unittest.TestCase):
    def test_inspection_reports_unprovisioned_empty_and_newer_schema(self) -> None:
        connection = Mock()
        connection.execute.return_value.fetchone.return_value = {"schema_exists": False}
        with patch(
            "clearspend.database.postgresql_migration_runner.database_connection",
            return_value=yielding(connection),
        ):
            status = inspect_postgresql_schema(Mock(), migrations=(synthetic_migration(1),))
        self.assertEqual(status.state, "unprovisioned")

        connection.execute.side_effect = [
            Mock(fetchone=Mock(return_value={"schema_exists": True})),
            Mock(fetchone=Mock(return_value={"table_exists": False})),
        ]
        with patch(
            "clearspend.database.postgresql_migration_runner.database_connection",
            return_value=yielding(connection),
        ):
            status = inspect_postgresql_schema(Mock(), migrations=(synthetic_migration(1),))
        self.assertEqual(status.state, "empty")

        connection.execute.side_effect = [
            Mock(fetchone=Mock(return_value={"schema_exists": True})),
            Mock(fetchone=Mock(return_value={"table_exists": True})),
            Mock(
                fetchall=Mock(
                    return_value=[
                        {"version": 1, "name": "synthetic_change"},
                        {"version": 2, "name": "unexpected_change"},
                    ]
                )
            ),
        ]
        with patch(
            "clearspend.database.postgresql_migration_runner.database_connection",
            return_value=yielding(connection),
        ):
            status = inspect_postgresql_schema(Mock(), migrations=(synthetic_migration(1),))
        self.assertEqual(status.state, "unsupported")
        self.assertEqual(status.version, 2)

    def test_migrations_must_be_contiguous_and_named(self) -> None:
        with self.assertRaisesRegex(PostgreSQLMigrationError, "contiguous"):
            migrate_postgresql(Mock(), migrations=(synthetic_migration(2),))
        with self.assertRaisesRegex(PostgreSQLMigrationError, "must have a name"):
            migrate_postgresql(Mock(), migrations=(synthetic_migration(1, ""),))

    def test_verified_migration_is_recorded_in_the_same_transaction(self) -> None:
        migration = synthetic_migration(1)
        connection = Mock()
        empty_status = Mock(state="empty", version=0, problems=())
        with patch(
            "clearspend.database.postgresql_migration_runner.inspect_postgresql_schema",
            return_value=empty_status,
        ), patch(
            "clearspend.database.postgresql_migration_runner.database_transaction",
            return_value=yielding(connection),
        ):
            result = migrate_postgresql(Mock(), migrations=(migration,))

        self.assertEqual(result.starting_version, 0)
        self.assertEqual(result.ending_version, 1)
        self.assertEqual(result.applied_versions, (1,))
        self.assertEqual(connection.execute.call_args_list[0].args, (MIGRATION_TABLE_SQL,))
        migration.apply.assert_called_once_with(connection)
        migration.verify.assert_called_once_with(connection)
        self.assertIn("INSERT INTO clearspend.schema_migrations", connection.execute.call_args_list[-1].args[0])
        self.assertEqual(connection.execute.call_args_list[-1].args[1], (1, "synthetic_change"))

    def test_failed_verification_is_not_recorded(self) -> None:
        migration = synthetic_migration(1)
        migration.verify.return_value = ["synthetic verification failure"]
        connection = Mock()
        with patch(
            "clearspend.database.postgresql_migration_runner.inspect_postgresql_schema",
            return_value=Mock(state="empty", version=0, problems=()),
        ), patch(
            "clearspend.database.postgresql_migration_runner.database_transaction",
            return_value=yielding(connection),
        ):
            with self.assertRaisesRegex(PostgreSQLMigrationError, "verification failed"):
                migrate_postgresql(Mock(), migrations=(migration,))

        executed_sql = [call.args[0] for call in connection.execute.call_args_list]
        self.assertFalse(any("INSERT INTO clearspend.schema_migrations" in sql for sql in executed_sql))

    def test_unprovisioned_schema_is_a_stop_condition(self) -> None:
        with patch(
            "clearspend.database.postgresql_migration_runner.inspect_postgresql_schema",
            return_value=Mock(state="unprovisioned", version=0, problems=("missing",)),
        ):
            with self.assertRaisesRegex(PostgreSQLMigrationError, "not provisioned"):
                migrate_postgresql(Mock(), migrations=(synthetic_migration(1),))


if __name__ == "__main__":
    unittest.main()
