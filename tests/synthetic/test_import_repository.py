from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, sentinel

from clearspend.import_engine import ImportDatabase as CompatibilityImportDatabase
from clearspend.import_engine import import_paths
from clearspend.database.settings import DatabaseBackend
from clearspend.imports.domain import ParsedStatement, Transaction
from clearspend.imports.metadata_policy import (
    POSTGRESQL_IMPORT_METADATA_POLICY,
    SQLITE_IMPORT_METADATA_POLICY,
    metadata_policy_for_backend,
)
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

        database.import_income.assert_called_once_with(
            source,
            original_name=None,
            commit=True,
        )
        database.import_statement.assert_called_once_with(
            source,
            probable_duplicate_matches={"candidate": 7},
            excluded_transaction_keys={"excluded"},
            original_name=None,
            commit=True,
        )

    def test_backend_policy_preserves_sqlite_metadata_and_minimizes_postgresql(self) -> None:
        source = Path("/synthetic/staging/random-upload.xlsx")
        self.assertIs(
            metadata_policy_for_backend(DatabaseBackend.SQLITE),
            SQLITE_IMPORT_METADATA_POLICY,
        )
        self.assertIs(
            metadata_policy_for_backend(DatabaseBackend.POSTGRESQL),
            POSTGRESQL_IMPORT_METADATA_POLICY,
        )
        self.assertEqual(
            SQLITE_IMPORT_METADATA_POLICY.source_path(source, "statement.xlsx"),
            str(source),
        )
        self.assertEqual(
            POSTGRESQL_IMPORT_METADATA_POLICY.source_path(source, "statement.xlsx"),
            "statement.xlsx",
        )
        self.assertEqual(
            SQLITE_IMPORT_METADATA_POLICY.error_message("synthetic detail"),
            "synthetic detail",
        )
        self.assertIsNone(
            POSTGRESQL_IMPORT_METADATA_POLICY.error_message("synthetic detail")
        )
        self.assertEqual(
            SQLITE_IMPORT_METADATA_POLICY.source_payload({"synthetic": True}),
            {"synthetic": True},
        )
        self.assertIsNone(
            POSTGRESQL_IMPORT_METADATA_POLICY.source_payload({"synthetic": True})
        )

    def test_postgresql_policy_is_applied_by_repository_writes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "random-upload.xlsx"
            source.write_bytes(b"synthetic statement")
            database = ImportDatabase(
                root / "synthetic.db",
                metadata_policy=POSTGRESQL_IMPORT_METADATA_POLICY,
            )
            try:
                with patch(
                    "clearspend.imports.repository.parse_statement",
                    side_effect=ValueError("synthetic detailed parser failure"),
                ):
                    failure = database.import_statement(
                        source,
                        original_name="statement-original.xlsx",
                    )
                failed_audit = database.connection.execute(
                    "SELECT original_name,source_path,error_message FROM imports WHERE id=?",
                    (failure["import_id"],),
                ).fetchone()

                income_source = root / "random-income-upload.xlsx"
                income_source.write_bytes(b"synthetic income")
                with patch(
                    "clearspend.imports.repository.parse_income_xlsx",
                    side_effect=ValueError("synthetic detailed income failure"),
                ):
                    income_failure = database.import_income(
                        income_source,
                        original_name="income-original.xlsx",
                    )
                failed_income_audit = database.connection.execute(
                    """SELECT original_name,source_path,error_message
                    FROM income_imports WHERE id=?""",
                    (income_failure["import_id"],),
                ).fetchone()

                transaction = Transaction(
                    provider="synthetic",
                    card_last4="0001",
                    source_sheet="synthetic-sheet",
                    transaction_date="2030-01-01",
                    billing_date="2030-02-01",
                    merchant_raw="Synthetic Merchant",
                    merchant_normalized="synthetic merchant",
                    charged_amount="10.00",
                    charged_currency="ILS",
                    original_amount="10.00",
                    original_currency="ILS",
                    source_payload={"synthetic": "raw"},
                )
                transaction.establish_identity()
                statement = ParsedStatement("synthetic", "0001", None, None, [transaction])
                source.write_bytes(b"different synthetic statement")
                with patch(
                    "clearspend.imports.repository.parse_statement",
                    return_value=statement,
                ):
                    success = database.import_statement(
                        source,
                        original_name="statement-second.xlsx",
                    )
                stored_payload = database.connection.execute(
                    "SELECT source_payload FROM transactions WHERE first_import_id=?",
                    (success["import_id"],),
                ).fetchone()[0]
            finally:
                database.close()

        self.assertEqual(
            dict(failed_audit),
            {
                "original_name": "statement-original.xlsx",
                "source_path": "statement-original.xlsx",
                "error_message": None,
            },
        )
        self.assertEqual(failure["error"], "synthetic detailed parser failure")
        self.assertEqual(
            dict(failed_income_audit),
            {
                "original_name": "income-original.xlsx",
                "source_path": "income-original.xlsx",
                "error_message": None,
            },
        )
        self.assertEqual(income_failure["error"], "synthetic detailed income failure")
        self.assertIsNone(stored_payload)

    def test_caller_owned_connection_selects_backend_policy_and_is_not_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database_path = root / "synthetic.db"
            initialized = ImportDatabase(database_path)
            initialized.close()
            connection = sqlite3.connect(database_path)
            connection.row_factory = sqlite3.Row
            source = root / "random-upload.xlsx"
            source.write_bytes(b"synthetic invalid statement")
            database = ImportDatabase.from_connection(
                connection,
                DatabaseBackend.POSTGRESQL,
            )
            with patch(
                "clearspend.imports.repository.parse_statement",
                side_effect=ValueError("synthetic parser detail"),
            ):
                result = database.import_statement(
                    source,
                    original_name="visible-name.xlsx",
                    commit=False,
                )
            database.close()
            stored = connection.execute(
                "SELECT source_path,error_message FROM imports WHERE id=?",
                (result["import_id"],),
            ).fetchone()
            connection.rollback()
            connection.close()

        self.assertEqual(stored["source_path"], "visible-name.xlsx")
        self.assertIsNone(stored["error_message"])

    def test_caller_managed_statement_transaction_does_not_commit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "synthetic.xlsx"
            source.write_bytes(b"synthetic statement")
            database_path = root / "synthetic.db"
            database = ImportDatabase(database_path)
            try:
                statement = ParsedStatement("synthetic", "0001", None, None, [])
                with patch("clearspend.imports.repository.parse_statement", return_value=statement):
                    result = database.import_statement(source, commit=False)

                observer = ImportDatabase(database_path)
                try:
                    self.assertEqual(
                        observer.connection.execute(
                            "SELECT COUNT(*) FROM imports WHERE id=?", (result["import_id"],)
                        ).fetchone()[0],
                        0,
                    )
                finally:
                    observer.close()

                database.connection.rollback()
                self.assertEqual(
                    database.connection.execute("SELECT COUNT(*) FROM imports").fetchone()[0],
                    0,
                )
            finally:
                database.close()

    @patch("clearspend.import_engine.ImportDatabase")
    def test_import_paths_always_closes_repository(self, database_type) -> None:
        database = database_type.return_value
        database.import_file.side_effect = RuntimeError("synthetic import failure")

        with self.assertRaisesRegex(RuntimeError, "synthetic import failure"):
            import_paths(Path("synthetic.db"), [Path("statement.xlsx")])

        database.close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
