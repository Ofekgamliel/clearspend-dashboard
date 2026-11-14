from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from clearspend.staging.file_analysis import (
    analyze_staged_income_file,
    analyze_staged_statement_file,
)
from tests.synthetic.support import add_income, connect, create_database


def transaction(key: str, **overrides):
    values = {
        "transaction_key": key,
        "base_key": f"base-{key}",
        "merchant_raw": "Synthetic Merchant",
        "merchant_normalized": "synthetic merchant",
        "transaction_date": "2030-02-10",
        "billing_date": "2030-03-02",
        "billing_month": "2030-03",
        "charged_amount": "40.00",
        "charged_currency": "ILS",
        "original_amount": None,
        "original_currency": None,
        "provider": "synthetic",
        "card_last4": "0001",
        "voucher_number": None,
        "installment_number": None,
        "installment_total": None,
        "notes": None,
        "source_sheet": "synthetic",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class StagingFileAnalysisTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database = Path(self.temporary_directory.name) / "synthetic.db"
        create_database(self.database)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_income_file_reports_existing_entry_without_writing(self) -> None:
        connection = connect(self.database)
        entry_id = add_income(
            connection,
            month="2030-02",
            source_name="Synthetic Income",
            amount=1000,
        )
        connection.commit()
        entry = SimpleNamespace(
            month="2030-02",
            source_name="Synthetic Income",
            amount="1000.00",
            entry_key="2030-02:synthetic income",
        )

        result = analyze_staged_income_file(
            connection,
            original_name="income.xlsx",
            path=Path("income.xlsx"),
            file_index=0,
            byte_hash="different-file-hash",
            entries=[entry],
        )
        connection.close()

        self.assertEqual(result["file"]["exact_duplicates"], 1)
        self.assertEqual(result["file"]["new_rows"], 0)
        self.assertEqual(result["exact_duplicates"][0]["matched_transaction_id"], entry_id)

    def test_statement_file_separates_new_and_pending_rows(self) -> None:
        connection = connect(self.database)
        statement = SimpleNamespace(
            transactions=[
                transaction("new"),
                transaction("pending", charged_amount=None),
            ],
            semantic_hash="synthetic-semantic-hash",
            provider="synthetic",
            card_last4="0001",
            product_name="Synthetic Card",
            date_range="2030-03",
            statement_as_of_date="2030-03-05",
            official_total=None,
        )

        result = analyze_staged_statement_file(
            connection,
            original_name="statement.xlsx",
            path=Path("statement.xlsx"),
            file_index=0,
            byte_hash="new-file-hash",
            statement=statement,
            seen_batch_keys={},
        )
        connection.close()

        self.assertEqual(result["file"]["new_rows"], 1)
        self.assertEqual(result["file"]["pending_rows"], 1)
        self.assertEqual(result["file"]["reconciliation"]["status"], "manual_required")
        self.assertEqual([item["transaction_key"] for item in result["new_transactions"]], ["new"])
        self.assertEqual([item["transaction_key"] for item in result["pending_transactions"]], ["pending"])


if __name__ == "__main__":
    unittest.main()
