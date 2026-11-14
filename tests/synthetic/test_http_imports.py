from __future__ import annotations

import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from clearspend.http.imports import (
    cancel_staged_import,
    commit_staged_import,
    process_import_uploads,
)
from clearspend.http.multipart import UploadedFile
from tests.synthetic.support import create_database


class HttpImportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.database = self.root / "synthetic.db"
        create_database(self.database)
        self.staged_imports: dict[str, dict] = {}

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_unsupported_upload_is_reported_without_writing_a_file(self) -> None:
        payload, status = process_import_uploads(
            self.database,
            self.staged_imports,
            [UploadedFile("synthetic.txt", BytesIO(b"not a statement"))],
        )

        self.assertEqual(status, 400)
        self.assertEqual(payload["error"], "Use one XLSX or PDF statement")
        self.assertFalse((self.root / "staging").exists())

    def test_multiple_files_are_rejected_before_any_file_is_written(self) -> None:
        payload, status = process_import_uploads(
            self.database,
            self.staged_imports,
            [
                UploadedFile("first.xlsx", BytesIO(b"first")),
                UploadedFile("second.xlsx", BytesIO(b"second")),
            ],
        )

        self.assertEqual(status, 400)
        self.assertIn("exactly one", payload["error"].lower())
        self.assertFalse((self.root / "staging").exists())
        self.assertEqual(self.staged_imports, {})

    @patch("clearspend.http.imports.analyze_staged_files")
    def test_staged_upload_is_persisted_and_registered(self, analyze) -> None:
        analyze.return_value = {"files": [], "merchants": []}

        payload, status = process_import_uploads(
            self.database,
            self.staged_imports,
            [UploadedFile("Synthetic statement.xlsx", BytesIO(b"synthetic workbook"))],
        )

        self.assertEqual(status, 200)
        batch = self.staged_imports[payload["batch_id"]]
        upload = batch["uploads"][0]
        self.assertEqual(upload["filename"], "Synthetic statement.xlsx")
        self.assertEqual(upload["path"].read_bytes(), b"synthetic workbook")
        self.assertEqual(payload["upload_errors"], [])
        analyze.assert_called_once()

    @patch("clearspend.http.imports.analyze_staged_files")
    def test_failed_staged_analysis_removes_temporary_files(self, analyze) -> None:
        analyze.side_effect = ValueError("Synthetic statement could not be analyzed")

        payload, status = process_import_uploads(
            self.database,
            self.staged_imports,
            [UploadedFile("synthetic.xlsx", BytesIO(b"invalid workbook"))],
        )

        self.assertEqual(status, 400)
        self.assertEqual(payload["error"], "Synthetic statement could not be analyzed")
        self.assertEqual(list((self.root / "staging").iterdir()), [])
        self.assertEqual(self.staged_imports, {})

    def test_cancel_staged_import_removes_temporary_files_without_database_writes(self) -> None:
        upload_path = self.root / "staged.xlsx"
        upload_path.write_bytes(b"synthetic")
        self.staged_imports["batch"] = {
            "uploads": [{"filename": "staged.xlsx", "path": upload_path}]
        }

        payload, status = cancel_staged_import(
            self.staged_imports, {"batch_id": "batch"}
        )

        self.assertEqual(status, 200)
        self.assertEqual(payload, {"status": "discarded", "removed": True})
        self.assertFalse(upload_path.exists())
        self.assertNotIn("batch", self.staged_imports)

    def test_cancel_missing_batch_is_idempotent(self) -> None:
        payload, status = cancel_staged_import(
            self.staged_imports, {"batch_id": "already-gone"}
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload, {"status": "discarded", "removed": False})

    def test_commit_rejects_a_forged_multi_file_session(self) -> None:
        self.staged_imports["batch"] = {
            "uploads": [
                {"filename": "first.xlsx", "path": self.root / "first.xlsx"},
                {"filename": "second.xlsx", "path": self.root / "second.xlsx"},
            ]
        }

        with self.assertRaisesRegex(ValueError, "Exactly one staged statement"):
            commit_staged_import(
                self.database,
                self.staged_imports,
                {"batch_id": "batch"},
            )

    @patch("clearspend.http.imports.commit_staged_statement")
    @patch("clearspend.http.imports.analyze_staged_files")
    def test_reconciliation_confirmation_is_required_before_commit(
        self, analyze, commit
    ) -> None:
        upload_path = self.root / "staged.xlsx"
        upload_path.write_bytes(b"synthetic")
        self.staged_imports["batch"] = {
            "uploads": [{"filename": "staged.xlsx", "path": upload_path}]
        }
        analyze.return_value = {
            "files": [{
                "filename": "staged.xlsx",
                "kind": "statement",
                "status": "ready",
                "reconciliation": {"status": "mismatch"},
            }]
        }

        with self.assertRaisesRegex(ValueError, "Confirm the statement total"):
            commit_staged_import(
                self.database,
                self.staged_imports,
                {"batch_id": "batch", "reconciled_files": []},
            )

        commit.assert_not_called()
        self.assertTrue(upload_path.exists())
        self.assertIn("batch", self.staged_imports)

    @patch("clearspend.http.imports.commit_staged_statement")
    @patch("clearspend.http.imports.analyze_staged_files")
    def test_successful_commit_removes_session_and_temporary_files(
        self, analyze, commit
    ) -> None:
        upload_path = self.root / "staged.xlsx"
        upload_path.write_bytes(b"synthetic")
        self.staged_imports["batch"] = {
            "uploads": [{"filename": "staged.xlsx", "path": upload_path}]
        }
        analyze.return_value = {
            "files": [{
                "filename": "staged.xlsx",
                "kind": "statement",
                "status": "ready",
                "reconciliation": {"status": "matched"},
            }]
        }
        commit.return_value = {"status": "committed", "results": []}

        payload, status = commit_staged_import(
            self.database,
            self.staged_imports,
            {"batch_id": "batch"},
        )

        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "committed")
        self.assertFalse(upload_path.exists())
        self.assertNotIn("batch", self.staged_imports)


if __name__ == "__main__":
    unittest.main()
