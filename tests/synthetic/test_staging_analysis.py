from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from clearspend.staging.analysis import (
    analyze_staged_files,
    possible_duplicate_matches,
    staged_reference_data,
    staged_statement_coverage,
    staged_transaction_summary,
    statement_reconciliation_total,
)
from tests.synthetic.support import add_import, add_transaction, connect, create_database


def transaction(**overrides):
    values = {
        "transaction_key": "synthetic-key",
        "merchant_raw": "Synthetic Merchant",
        "merchant_normalized": "synthetic merchant",
        "transaction_date": "2030-02-10",
        "billing_date": "2030-03-02",
        "billing_month": "2030-03",
        "charged_amount": 40.0,
        "charged_currency": "ILS",
        "original_amount": None,
        "original_currency": None,
        "provider": "synthetic",
        "card_last4": "0001",
        "voucher_number": None,
        "installment_number": None,
        "installment_total": None,
        "notes": "Synthetic note",
        "source_sheet": "synthetic",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class StagingAnalysisTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database = Path(self.temporary_directory.name) / "synthetic.db"
        create_database(self.database)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_transaction_summary_distinguishes_monthly_pending_and_outside_cycle(self) -> None:
        monthly = staged_transaction_summary(transaction(), "statement.xlsx", 2)
        pending = staged_transaction_summary(
            transaction(charged_amount=None), "statement.xlsx", 2
        )
        outside = staged_transaction_summary(
            transaction(source_sheet="synthetic:immediate"), "statement.xlsx", 2
        )

        self.assertEqual(monthly["source_status"], "monthly")
        self.assertEqual(pending["source_status"], "pending")
        self.assertEqual(outside["source_status"], "outside_cycle")
        self.assertEqual(monthly["filename"], "statement.xlsx")
        self.assertEqual(monthly["file_index"], 2)

    def test_reconciliation_excludes_immediate_and_treats_pending_as_zero(self) -> None:
        statement = SimpleNamespace(transactions=[
            transaction(charged_amount=100),
            transaction(transaction_key="immediate", charged_amount=25, source_sheet="synthetic:immediate"),
            transaction(transaction_key="pending", charged_amount=None),
        ])

        self.assertEqual(statement_reconciliation_total(statement), 100)

    def test_duplicate_matching_uses_voucher_before_fallback_fields(self) -> None:
        connection = connect(self.database)
        import_id = add_import(connection)
        transaction_id = add_transaction(
            connection, import_id, key="existing", merchant="Synthetic Merchant",
            amount=40, category="Household", transaction_date="2030-02-10",
        )
        connection.execute(
            """UPDATE transactions SET voucher_number='voucher-1',billing_date='2030-03-02',
            charged_currency='ILS' WHERE id=?""",
            (transaction_id,),
        )
        connection.commit()

        rows, reason = possible_duplicate_matches(
            connection,
            transaction(transaction_key="changed-key", voucher_number="voucher-1"),
        )
        connection.close()

        self.assertEqual([row["id"] for row in rows], [transaction_id])
        self.assertIn("provider reference", reason)

    def test_coverage_reports_overlap_and_gap_from_prior_imports(self) -> None:
        connection = connect(self.database)
        import_id = add_import(connection, name="prior-statement.xlsx")
        connection.execute(
            """INSERT INTO import_coverage(
            import_id,card_last4,statement_month,purchase_date_from,purchase_date_to,
            finalized_rows
            ) VALUES(?,?,?,?,?,?)""",
            (import_id, "0001", "2030-01", "2030-01-15", "2030-02-05", 2),
        )
        connection.commit()
        statement = SimpleNamespace(
            transactions=[
                transaction(transaction_date="2030-02-01", billing_date="2030-03-02"),
                transaction(
                    transaction_key="pending", transaction_date="2030-02-20",
                    billing_date=None, charged_amount=None,
                ),
            ],
            date_range="2030-03",
            statement_as_of_date="2030-03-05",
            official_total=40,
        )

        coverage, warnings = staged_statement_coverage(connection, statement)
        connection.close()

        self.assertEqual(coverage[0]["purchase_date_from"], "2030-02-01")
        self.assertEqual(coverage[0]["purchase_date_to"], "2030-02-20")
        self.assertEqual(coverage[0]["finalized_rows"], 1)
        self.assertEqual(coverage[0]["pending_rows"], 1)
        self.assertEqual({item["type"] for item in warnings}, {"overlap", "coverage_gap"})

    def test_reference_data_marks_mixed_display_identity_categories(self) -> None:
        connection = connect(self.database)
        import_id = add_import(connection)
        alpha = "Synthetic Alpha".casefold()
        beta = "Synthetic Beta".casefold()
        add_transaction(
            connection, import_id, key="alpha", merchant="Synthetic Alpha",
            amount=10, category="Category A",
        )
        add_transaction(
            connection, import_id, key="beta", merchant="Synthetic Beta",
            amount=20, category="Category B",
        )
        for alias, category in ((alpha, "Category A"), (beta, "Category B")):
            connection.execute(
                """INSERT INTO merchant_display_mappings(
                merchant_normalized,canonical_group_id,display_name,updated_at
                ) VALUES(?,?,?,?)""",
                (alias, "synthetic-group", "Synthetic Brand", "2030-01-15T00:00:00"),
            )
            connection.execute(
                """INSERT INTO merchant_mappings(
                merchant_normalized,category,subcategory,updated_at
                ) VALUES(?,?,NULL,?)""",
                (alias, category, "2030-01-15T00:00:00"),
            )
        connection.commit()

        categories, identities = staged_reference_data(connection)
        connection.close()

        self.assertEqual(categories, ["Category A", "Category B"])
        self.assertEqual(len(identities), 1)
        self.assertEqual(identities[0]["category_status"], "mixed")
        self.assertIsNone(identities[0]["category"])
        self.assertEqual(identities[0]["alias_names"], [alpha, beta])

    def test_staged_file_analysis_classifies_rows_without_writing(self) -> None:
        connection = connect(self.database)
        import_id = add_import(connection)
        add_transaction(
            connection, import_id, key="existing-key", merchant="Synthetic Existing",
            amount=40, category="Household", transaction_date="2030-02-10",
            billing_month="2030-03",
        )
        connection.execute(
            """INSERT INTO merchant_mappings(
            merchant_normalized,category,subcategory,updated_at
            ) VALUES(?,?,NULL,?)""",
            ("synthetic new", "Travel", "2030-01-15T00:00:00"),
        )
        connection.commit()
        before = connection.total_changes
        connection.close()
        existing = transaction(
            transaction_key="existing-key", base_key="base-existing-key",
            merchant_raw="Synthetic Existing", merchant_normalized="synthetic existing",
            provider_category="Household",
        )
        new = transaction(
            transaction_key="new-key", base_key="base-new-key",
            merchant_raw="Synthetic New", merchant_normalized="synthetic new",
            charged_amount=60, provider_category="Travel",
        )
        pending = transaction(
            transaction_key="pending-key", base_key="base-pending-key",
            merchant_raw="Synthetic Pending", merchant_normalized="synthetic pending",
            charged_amount=None, provider_category=None,
        )
        statement = SimpleNamespace(
            transactions=[existing, new, pending],
            semantic_hash="synthetic-semantic-hash",
            provider="synthetic",
            card_last4="0001",
            product_name="Synthetic Card",
            date_range="2030-03",
            statement_as_of_date="2030-03-05",
            official_total=100,
        )
        path = self.database.parent / "synthetic-statement.json"

        with patch("clearspend.staging.analysis.sha256_path", return_value="new-file-hash"), \
                patch("clearspend.staging.analysis.parse_statement", return_value=statement):
            payload = analyze_staged_files(
                self.database, [("synthetic-statement.json", path)]
            )

        connection = connect(self.database)
        after_counts = {
            "transactions": connection.execute("SELECT COUNT(*) FROM transactions").fetchone()[0],
            "imports": connection.execute("SELECT COUNT(*) FROM imports").fetchone()[0],
            "total_changes": connection.total_changes,
        }
        connection.close()
        self.assertEqual(payload["files"][0]["exact_duplicates"], 1)
        self.assertEqual(payload["files"][0]["new_rows"], 1)
        self.assertEqual(payload["files"][0]["pending_rows"], 1)
        self.assertEqual(payload["files"][0]["reconciliation"]["status"], "matched")
        self.assertEqual(len(payload["exact_duplicates"]), 1)
        self.assertEqual(len(payload["new_transactions"]), 1)
        self.assertEqual(len(payload["pending_transactions"]), 1)
        self.assertEqual(payload["merchants"][0]["match_source"], "exact_db")
        self.assertFalse(payload["merchants"][0]["needs_review"])
        self.assertEqual(after_counts, {"transactions": 1, "imports": 1, "total_changes": 0})
        self.assertGreater(before, 0)


if __name__ == "__main__":
    unittest.main()
