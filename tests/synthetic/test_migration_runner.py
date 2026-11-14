from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from clearspend.database.migration_runner import (
    MigrationError,
    inspect_database,
    migrate_database,
)
from clearspend.database.migrations import v001_current_baseline
from clearspend.import_engine import ImportDatabase
from tools.verify_migration_copy import verify_copy


def create_unversioned_database(path: Path) -> None:
    connection = sqlite3.connect(path)
    try:
        v001_current_baseline.apply(connection)
        connection.commit()
    finally:
        connection.close()


class SyntheticMigrationRunnerTests(unittest.TestCase):
    def test_empty_database_is_created_at_version_one(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "new.db"
            result = migrate_database(path)

            self.assertEqual((result.starting_version, result.ending_version), (0, 1))
            self.assertEqual(result.applied_versions, (1,))
            self.assertIsNone(result.backup_path)
            self.assertEqual(inspect_database(path).state, "versioned")

    def test_current_unversioned_database_is_registered_after_backup(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "existing.db"
            create_unversioned_database(path)
            database = ImportDatabase(path)
            try:
                database.connection.execute(
                    """INSERT INTO merchant_mappings(
                    merchant_normalized,category,subcategory,updated_at
                    ) VALUES('synthetic merchant','Synthetic category',NULL,'2030-01-01')"""
                )
                database.connection.commit()
            finally:
                database.close()

            result = migrate_database(path, root / "backups")

            self.assertEqual(result.applied_versions, (1,))
            self.assertIsNotNone(result.backup_path)
            self.assertTrue(result.backup_path.is_file())
            connection = sqlite3.connect(path)
            backup = sqlite3.connect(result.backup_path)
            try:
                self.assertEqual(
                    connection.execute("SELECT category FROM merchant_mappings").fetchone()[0],
                    "Synthetic category",
                )
                self.assertEqual(
                    backup.execute("SELECT category FROM merchant_mappings").fetchone()[0],
                    "Synthetic category",
                )
            finally:
                connection.close()
                backup.close()

    def test_second_run_is_a_no_op_without_another_backup(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "repeat.db"
            first = migrate_database(path)
            second = migrate_database(path, root / "backups")

            self.assertEqual(first.applied_versions, (1,))
            self.assertEqual(second.applied_versions, ())
            self.assertIsNone(second.backup_path)
            self.assertFalse((root / "backups").exists())

    def test_unknown_partial_schema_is_rejected_without_metadata_write(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "partial.db"
            connection = sqlite3.connect(path)
            connection.execute("CREATE TABLE transactions(id INTEGER PRIMARY KEY)")
            connection.commit()
            connection.close()

            with self.assertRaisesRegex(MigrationError, "Unsupported unversioned schema"):
                migrate_database(path, Path(directory) / "backups")

            connection = sqlite3.connect(path)
            try:
                tables = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    )
                }
            finally:
                connection.close()
            self.assertEqual(tables, {"transactions"})
            self.assertFalse((Path(directory) / "backups").exists())

    def test_failing_future_migration_rolls_back_its_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "failure.db"
            migrate_database(path)

            def fail_after_write(connection: sqlite3.Connection) -> None:
                connection.execute("CREATE TABLE should_rollback(id INTEGER PRIMARY KEY)")
                raise RuntimeError("synthetic migration failure")

            future = SimpleNamespace(
                VERSION=2,
                NAME="synthetic_failure",
                apply=fail_after_write,
                verify=lambda connection: [],
            )
            from clearspend.database.migrations import v001_current_baseline

            with self.assertRaisesRegex(RuntimeError, "synthetic migration failure"):
                migrate_database(
                    path,
                    root / "backups",
                    migrations=(v001_current_baseline, future),
                )

            connection = sqlite3.connect(path)
            try:
                tables = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    )
                }
                versions = [
                    row[0]
                    for row in connection.execute(
                        "SELECT version FROM schema_migrations ORDER BY version"
                    )
                ]
            finally:
                connection.close()
            self.assertNotIn("should_rollback", tables)
            self.assertEqual(versions, [1])

    def test_copy_verifier_migrates_only_the_temporary_copy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.db"
            create_unversioned_database(source)
            database = ImportDatabase(source)
            try:
                database.connection.execute(
                    """INSERT INTO merchant_mappings(
                    merchant_normalized,category,subcategory,updated_at
                    ) VALUES('synthetic source','Synthetic category',NULL,'2030-01-01')"""
                )
                database.connection.commit()
            finally:
                database.close()

            result = verify_copy(source, root / "verification")

            self.assertEqual(result["status"], "verified")
            self.assertTrue(result["source_unchanged"])
            self.assertEqual(result["copy_version"], 1)
            connection = sqlite3.connect(source)
            try:
                version_table = connection.execute(
                    """SELECT COUNT(*) FROM sqlite_master
                    WHERE type='table' AND name='schema_migrations'"""
                ).fetchone()[0]
            finally:
                connection.close()
            self.assertEqual(version_table, 0)

    def test_import_database_creates_a_fresh_versioned_database(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fresh.db"

            database = ImportDatabase(path)
            database.close()

            self.assertEqual(inspect_database(path).state, "versioned")

    def test_import_database_does_not_register_an_existing_compatible_database(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "compatible.db"
            create_unversioned_database(path)

            before = path.read_bytes()
            database = ImportDatabase(path)
            database.close()

            self.assertEqual(inspect_database(path).state, "current_unversioned")
            self.assertEqual(path.read_bytes(), before)

    def test_import_database_rejects_an_incompatible_database(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "incompatible.db"
            connection = sqlite3.connect(path)
            connection.execute("CREATE TABLE transactions(id INTEGER PRIMARY KEY)")
            connection.commit()
            connection.close()

            with self.assertRaisesRegex(MigrationError, "Unsupported database schema"):
                ImportDatabase(path)


if __name__ == "__main__":
    unittest.main()
