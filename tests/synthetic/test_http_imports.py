from __future__ import annotations

import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from clearspend.http.imports import commit_staged_import, process_import_uploads
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
            staged=False,
        )

        self.assertEqual(status, 200)
        self.assertEqual(payload["results"][0]["status"], "unsupported")
        self.assertEqual(list((self.root / "uploads").iterdir()), [])

    @patch("clearspend.http.imports.ImportDatabase")
    def test_direct_upload_records_original_filename_and_closes_importer(
        self, importer_class
    ) -> None:
        importer = importer_class.return_value
        importer.import_file.return_value = {
            "status": "imported",
            "kind": "statement",
            "import_id": 7,
        }

        payload, status = process_import_uploads(
            self.database,
            self.staged_imports,
            [UploadedFile("Synthetic statement.xlsx", BytesIO(b"synthetic workbook"))],
            staged=False,
        )

        self.assertEqual(status, 200)
        self.assertEqual(payload["results"][0]["filename"], "Synthetic statement.xlsx")
        importer.connection.execute.assert_called_once_with(
            "UPDATE imports SET original_name = ? WHERE id = ?",
            ("Synthetic statement.xlsx", 7),
        )
        importer.connection.commit.assert_called_once_with()
        importer.close.assert_called_once_with()
        uploads = list((self.root / "uploads").iterdir())
        self.assertEqual(len(uploads), 1)
        self.assertEqual(uploads[0].read_bytes(), b"synthetic workbook")

    @patch("clearspend.http.imports.ImportDatabase")
    def test_direct_duplicate_upload_removes_temporary_file(self, importer_class) -> None:
        importer_class.return_value.import_file.return_value = {
            "status": "duplicate_content"
        }

        payload, status = process_import_uploads(
            self.database,
            self.staged_imports,
            [UploadedFile("duplicate.xlsx", BytesIO(b"synthetic duplicate"))],
            staged=False,
        )

        self.assertEqual(status, 200)
        self.assertEqual(payload["results"][0]["status"], "duplicate_content")
        self.assertEqual(list((self.root / "uploads").iterdir()), [])
        importer_class.return_value.close.assert_called_once_with()

    @patch("clearspend.http.imports.analyze_staged_files")
    def test_staged_upload_is_persisted_and_registered(self, analyze) -> None:
        analyze.return_value = {"files": [], "merchants": []}

        payload, status = process_import_uploads(
            self.database,
            self.staged_imports,
            [UploadedFile("Synthetic statement.xlsx", BytesIO(b"synthetic workbook"))],
            staged=True,
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
            staged=True,
        )

        self.assertEqual(status, 400)
        self.assertEqual(payload["error"], "Synthetic statement could not be analyzed")
        self.assertEqual(payload["results"], [])
        self.assertEqual(list((self.root / "staging").iterdir()), [])
        self.assertEqual(self.staged_imports, {})

    @patch("clearspend.http.imports.commit_staged_batch")
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

    @patch("clearspend.http.imports.commit_staged_batch")
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
