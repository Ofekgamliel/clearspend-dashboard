from __future__ import annotations

import tempfile
import unittest
import sqlite3
from pathlib import Path
from unittest.mock import patch

from clearspend.database.backup import DatabaseBackupError
from clearspend.import_engine import ImportDatabase
from clearspend.staging.service import commit_staged_statement
from tests.synthetic.support import add_import, add_transaction, connect, create_database


class StagingServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database = Path(self.temporary_directory.name) / "synthetic.db"
        create_database(self.database)
        connection = connect(self.database)
        import_id = add_import(connection)
        add_transaction(
            connection, import_id, key="existing", merchant="Synthetic Existing",
            amount=25, category="Household",
        )
        connection.commit()
        connection.close()

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def database_counts(self) -> tuple[int, int, int]:
        connection = connect(self.database)
        try:
            return (
                connection.execute("SELECT COUNT(*) FROM transactions").fetchone()[0],
                connection.execute("SELECT COUNT(*) FROM merchant_mappings").fetchone()[0],
                connection.execute("SELECT COUNT(*) FROM merchant_display_mappings").fetchone()[0],
            )
        finally:
            connection.close()

    def staged_upload(self) -> dict:
        path = Path(self.temporary_directory.name) / "staged.xlsx"
        path.write_bytes(b"synthetic staged file")
        return {"uploads": [{"filename": "staged.xlsx", "path": path}]}

    @staticmethod
    def analysis() -> dict:
        return {
            "possible_duplicates": [],
            "merchants": [],
            "pending_transactions": [],
            "files": [{"coverage": []}],
        }

    def test_unreviewed_possible_duplicate_is_rejected_without_database_changes(self) -> None:
        before = self.database_counts()
        analysis = {
            "possible_duplicates": [{
                "candidate_id": "candidate-1",
                "file_index": 0,
                "transaction_key": "incoming-key",
                "matched_transaction_ids": [1],
            }],
            "merchants": [],
            "pending_transactions": [],
            "files": [],
        }

        with self.assertRaisesRegex(ValueError, "must be reviewed"):
            commit_staged_statement(
                self.database, self.staged_upload(), [], [], analysis
            )

        self.assertEqual(self.database_counts(), before)
        backups = list((self.database.parent / "backups").glob("clearspend-before-import-*.db"))
        self.assertEqual(len(backups), 0)

    def test_invalid_link_decision_rolls_back_mapping_changes(self) -> None:
        before = self.database_counts()
        analysis = {
            "possible_duplicates": [],
            "merchants": [],
            "pending_transactions": [],
            "files": [],
        }
        decisions = [{
            "merchant_normalized": "synthetic incoming",
            "resolution": "link",
            "scope": "batch",
            "category": "Travel",
            "display_name": "Synthetic Existing",
            "canonical_group_id": "synthetic existing",
        }]

        with self.assertRaisesRegex(ValueError, "permanent exact-name scope"):
            commit_staged_statement(
                self.database, self.staged_upload(), decisions, [], analysis
            )

        self.assertEqual(self.database_counts(), before)

    def test_failure_after_merchant_decisions_rolls_back_everything(self) -> None:
        before = self.database_counts()
        decisions = [{
            "merchant_normalized": "synthetic incoming",
            "resolution": "create",
            "scope": "exact",
            "category": "Travel",
            "display_name": "Synthetic Incoming",
            "canonical_group_id": "",
        }]

        with patch.object(
            ImportDatabase,
            "import_file",
            autospec=True,
            side_effect=RuntimeError("synthetic persistence failure"),
        ) as import_file:
            with self.assertRaisesRegex(RuntimeError, "synthetic persistence failure"):
                commit_staged_statement(
                    self.database,
                    self.staged_upload(),
                    decisions,
                    [],
                    self.analysis(),
                )

        self.assertEqual(self.database_counts(), before)
        self.assertFalse(import_file.call_args.kwargs["commit"])

    def test_failure_during_coverage_rolls_back_import_audit(self) -> None:
        def write_import(database: ImportDatabase, *args, **kwargs) -> dict:
            cursor = database.connection.execute(
                """INSERT INTO imports(
                original_name,source_path,byte_hash,source_format,provider,card_last4,
                status,parsed_rows,inserted_rows,imported_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (
                    "staged.xlsx", "staged.xlsx", "staged-hash", ".xlsx", "synthetic",
                    "0001", "imported", 0, 0, "2030-01-15T10:00:00",
                ),
            )
            return {
                "import_id": cursor.lastrowid,
                "status": "imported",
                "kind": "statement",
                "inserted": 0,
            }

        connection = sqlite3.connect(self.database)
        try:
            before_imports = connection.execute("SELECT COUNT(*) FROM imports").fetchone()[0]
        finally:
            connection.close()
        with patch.object(ImportDatabase, "import_file", autospec=True, side_effect=write_import), patch(
            "clearspend.staging.service.save_import_coverage",
            side_effect=RuntimeError("synthetic coverage failure"),
        ):
            with self.assertRaisesRegex(RuntimeError, "synthetic coverage failure"):
                commit_staged_statement(
                    self.database,
                    self.staged_upload(),
                    [],
                    [],
                    self.analysis(),
                )

        connection = sqlite3.connect(self.database)
        try:
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM imports").fetchone()[0],
                before_imports,
            )
        finally:
            connection.close()

    def test_backup_failure_prevents_import(self) -> None:
        before = self.database_counts()
        with patch(
            "clearspend.staging.service.create_verified_backup",
            side_effect=DatabaseBackupError("synthetic backup failure"),
        ), patch.object(ImportDatabase, "import_file", autospec=True) as import_file:
            with self.assertRaisesRegex(DatabaseBackupError, "synthetic backup failure"):
                commit_staged_statement(
                    self.database,
                    self.staged_upload(),
                    [],
                    [],
                    self.analysis(),
                )

        self.assertEqual(self.database_counts(), before)
        import_file.assert_not_called()

    def test_successful_import_commits_once_as_a_complete_unit(self) -> None:
        def write_income_import(database: ImportDatabase, *args, **kwargs) -> dict:
            cursor = database.connection.execute(
                """INSERT INTO income_imports(
                original_name,source_path,byte_hash,source_format,status,
                parsed_rows,inserted_rows,imported_at
                ) VALUES(?,?,?,?,?,?,?,?)""",
                (
                    "staged.xlsx", "staged.xlsx", "income-hash", ".xlsx", "imported",
                    0, 0, "2030-01-15T10:00:00",
                ),
            )
            return {
                "import_id": cursor.lastrowid,
                "status": "imported",
                "kind": "income",
                "inserted": 0,
            }

        with patch.object(
            ImportDatabase,
            "import_file",
            autospec=True,
            side_effect=write_income_import,
        ) as import_file:
            result = commit_staged_statement(
                self.database,
                self.staged_upload(),
                [],
                [],
                self.analysis(),
            )

        self.assertEqual(result["status"], "committed")
        self.assertTrue(Path(result["backup"]).is_file())
        self.assertFalse(import_file.call_args.kwargs["commit"])
        connection = sqlite3.connect(self.database)
        try:
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM income_imports").fetchone()[0],
                1,
            )
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
