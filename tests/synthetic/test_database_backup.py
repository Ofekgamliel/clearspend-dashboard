from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from clearspend.database.backup import DatabaseBackupError, create_verified_backup


class DatabaseBackupTests(unittest.TestCase):
    def test_backup_captures_a_wal_database_and_restores_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "synthetic.db"
            writer = sqlite3.connect(database)
            writer.execute("PRAGMA journal_mode=WAL")
            writer.execute("CREATE TABLE values_table(value TEXT NOT NULL)")
            writer.execute("INSERT INTO values_table VALUES('synthetic')")
            writer.commit()

            source = sqlite3.connect(database)
            try:
                backup_path = create_verified_backup(
                    source,
                    database,
                    root / "backups",
                    "before-test",
                )
            finally:
                source.close()
                writer.close()

            restored = sqlite3.connect(backup_path)
            try:
                self.assertEqual(restored.execute("PRAGMA integrity_check").fetchone()[0], "ok")
                self.assertEqual(
                    restored.execute("SELECT value FROM values_table").fetchone()[0],
                    "synthetic",
                )
            finally:
                restored.close()

    def test_invalid_source_stops_before_creating_a_backup(self) -> None:
        source = MagicMock()
        source.execute.return_value.fetchone.return_value = ("synthetic corruption",)
        with tempfile.TemporaryDirectory() as directory:
            backup_directory = Path(directory) / "backups"

            with self.assertRaisesRegex(DatabaseBackupError, "Source database integrity"):
                create_verified_backup(
                    source,
                    Path(directory) / "synthetic.db",
                    backup_directory,
                    "before-test",
                )

            source.backup.assert_not_called()
            self.assertFalse(backup_directory.exists())


if __name__ == "__main__":
    unittest.main()
