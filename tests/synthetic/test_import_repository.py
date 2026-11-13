from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, sentinel

from clearspend.import_engine import ImportDatabase as CompatibilityImportDatabase
from clearspend.import_engine import import_paths
from clearspend.imports.repository import ImportDatabase


class ImportRepositoryTests(unittest.TestCase):
    def test_compatibility_facade_exports_repository(self) -> None:
        self.assertIs(CompatibilityImportDatabase, ImportDatabase)

    def test_failed_statement_parse_is_recorded_in_import_audit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "invalid-statement.xlsx"
            source.write_bytes(b"synthetic invalid statement")
            database = ImportDatabase(root / "synthetic.db")
            try:
                with patch(
                    "clearspend.imports.repository.parse_statement",
                    side_effect=ValueError("synthetic parse failure"),
                ):
                    result = database.import_statement(source)
                audit = database.connection.execute(
                    "SELECT original_name,status,error_message FROM imports WHERE id=?",
                    (result["import_id"],),
                ).fetchone()
            finally:
                database.close()

        self.assertEqual(result["status"], "failed")
        self.assertEqual(dict(audit), {
            "original_name": source.name,
            "status": "failed",
            "error_message": "synthetic parse failure",
        })

    def test_import_file_routes_income_and_statement_inputs(self) -> None:
        database = object.__new__(ImportDatabase)
        database.import_income = MagicMock(return_value=sentinel.income)
        database.import_statement = MagicMock(return_value=sentinel.statement)
        source = Path("synthetic.xlsx")

        with patch("clearspend.imports.repository.is_income_xlsx", side_effect=[True, False]):
            self.assertIs(database.import_file(source), sentinel.income)
            self.assertIs(
                database.import_file(
                    source,
                    probable_duplicate_matches={"candidate": 7},
                    excluded_transaction_keys={"excluded"},
                ),
                sentinel.statement,
            )

        database.import_income.assert_called_once_with(source)
        database.import_statement.assert_called_once_with(
            source,
            probable_duplicate_matches={"candidate": 7},
            excluded_transaction_keys={"excluded"},
        )

    @patch("clearspend.import_engine.ImportDatabase")
    def test_import_paths_always_closes_repository(self, database_type) -> None:
        database = database_type.return_value
        database.import_file.side_effect = RuntimeError("synthetic import failure")

        with self.assertRaisesRegex(RuntimeError, "synthetic import failure"):
            import_paths(Path("synthetic.db"), [Path("statement.xlsx")])

        database.close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
