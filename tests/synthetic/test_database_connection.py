from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock

from clearspend.database.connection import (
    connect_database,
    database_connection,
    database_transaction,
)
from clearspend.database.postgresql import PostgreSQLPool
from clearspend.database.settings import (
    DatabaseBackend,
    DatabaseSettings,
    PostgreSQLSettings,
    normalize_database_settings,
)


class DatabaseConnectionTests(unittest.TestCase):
    def test_default_connection_returns_named_rows_without_changing_foreign_key_behavior(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            connection = connect_database(Path(directory) / "synthetic.db")
            try:
                row = connection.execute("SELECT 7 AS synthetic_value").fetchone()
                foreign_keys = connection.execute("PRAGMA foreign_keys").fetchone()[0]
            finally:
                connection.close()

        self.assertIsInstance(row, sqlite3.Row)
        self.assertEqual(row["synthetic_value"], 7)
        self.assertEqual(foreign_keys, 0)

    def test_foreign_key_enforcement_is_explicitly_available(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            connection = connect_database(
                Path(directory) / "synthetic.db",
                enforce_foreign_keys=True,
            )
            try:
                foreign_keys = connection.execute("PRAGMA foreign_keys").fetchone()[0]
            finally:
                connection.close()

        self.assertEqual(foreign_keys, 1)

    def test_row_factory_can_be_disabled_for_low_level_callers(self) -> None:
        connection = connect_database(":memory:", row_factory=None)
        try:
            row = connection.execute("SELECT 11").fetchone()
        finally:
            connection.close()

        self.assertEqual(row, (11,))

    def test_explicit_sqlite_settings_use_the_same_connection_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic.db"
            settings = DatabaseSettings.sqlite(path)
            connection = connect_database(settings)
            try:
                row = connection.execute("SELECT 13 AS synthetic_value").fetchone()
            finally:
                connection.close()

        self.assertEqual(settings.backend, DatabaseBackend.SQLITE)
        self.assertEqual(settings.sqlite_path, path)
        self.assertEqual(row["synthetic_value"], 13)

    def test_legacy_path_is_normalized_to_explicit_sqlite_settings(self) -> None:
        settings = normalize_database_settings("synthetic.db")

        self.assertEqual(settings, DatabaseSettings.sqlite(Path("synthetic.db")))

    def test_unavailable_postgresql_selection_never_falls_back_to_sqlite(self) -> None:
        settings = PostgreSQLSettings(
            host="db.synthetic.invalid",
            port=5432,
            database="postgres",
            user="clearspend_app",
            ssl_root_certificate=Path("synthetic-ca.crt"),
            keychain_service="clearspend-synthetic",
            keychain_account="clearspend_app",
        )
        with self.assertRaisesRegex(RuntimeError, "explicitly opened PostgreSQLPool"):
            connect_database(DatabaseSettings.postgresql(settings))

    def test_backend_settings_reject_mixed_or_incomplete_configuration(self) -> None:
        with self.assertRaisesRegex(ValueError, "SQLite database path is required"):
            DatabaseSettings(DatabaseBackend.SQLITE)
        with self.assertRaisesRegex(ValueError, "cannot contain a SQLite path"):
            DatabaseSettings(
                DatabaseBackend.POSTGRESQL,
                Path("synthetic.db"),
                PostgreSQLSettings(
                    host="db.synthetic.invalid",
                    port=5432,
                    database="postgres",
                    user="clearspend_app",
                    ssl_root_certificate=Path("synthetic-ca.crt"),
                    keychain_service="clearspend-synthetic",
                    keychain_account="clearspend_app",
                ),
            )

    def test_database_transaction_commits_success_and_rolls_back_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic.db"
            with database_connection(path) as connection:
                connection.execute("CREATE TABLE items(value TEXT NOT NULL)")

            with database_transaction(path) as connection:
                connection.execute("INSERT INTO items(value) VALUES(?)", ("kept",))

            with self.assertRaisesRegex(RuntimeError, "synthetic failure"):
                with database_transaction(path) as connection:
                    connection.execute("INSERT INTO items(value) VALUES(?)", ("removed",))
                    raise RuntimeError("synthetic failure")

            with database_connection(path) as connection:
                rows = connection.execute("SELECT value FROM items ORDER BY value").fetchall()

        self.assertEqual([row["value"] for row in rows], ["kept"])

    def test_open_postgresql_pool_uses_shared_connection_boundaries(self) -> None:
        settings = PostgreSQLSettings(
            host="db.synthetic.invalid",
            port=5432,
            database="postgres",
            user="clearspend_app",
            ssl_root_certificate=Path("synthetic-ca.crt"),
            keychain_service="clearspend-synthetic",
            keychain_account="clearspend_app",
        )
        pool = PostgreSQLPool(settings, password_loader=Mock())
        connection = Mock()
        connection_context = MagicMock()
        connection_context.__enter__.return_value = connection
        pool.connection = Mock(return_value=connection_context)

        with database_connection(pool) as yielded:
            self.assertIs(yielded, connection)

        with database_transaction(pool) as yielded:
            self.assertIs(yielded, connection)

        with self.assertRaisesRegex(RuntimeError, "synthetic failure"):
            with database_transaction(pool):
                raise RuntimeError("synthetic failure")

        self.assertEqual(pool.connection.call_count, 3)
        self.assertEqual(connection.execute.call_count, 2)
        connection.execute.assert_called_with(
            "SELECT pg_advisory_xact_lock(?)",
            (1_127_033_681,),
        )
        connection.commit.assert_called_once_with()
        connection.rollback.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
