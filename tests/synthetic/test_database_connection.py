from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from clearspend.database.connection import connect_database


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


if __name__ == "__main__":
    unittest.main()
