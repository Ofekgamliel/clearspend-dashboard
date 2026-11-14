from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from clearspend.transactions.service import (
    save_transaction_adjustment,
    save_transaction_category,
)
from tests.synthetic.support import add_import, add_transaction, connect, create_database


class TransactionServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database = Path(self.temporary_directory.name) / "synthetic.db"
        create_database(self.database)
        connection = connect(self.database)
        try:
            import_id = add_import(connection)
            self.transaction_id = add_transaction(
                connection, import_id, key="corrected-purchase", merchant="Synthetic Shop",
                amount=100, category="Original category",
            )
            connection.execute(
                """INSERT INTO merchant_mappings(
                merchant_normalized,category,subcategory,updated_at
                ) VALUES('synthetic shop','Original category',NULL,'2030-01-01')"""
            )
            connection.commit()
        finally:
            connection.close()

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_category_override_does_not_change_permanent_merchant_rule(self) -> None:
        result = save_transaction_category(
            self.database, self.transaction_id, "Exceptional category", "One purchase"
        )

        self.assertEqual(result["category"], "Exceptional category")
        connection = connect(self.database)
        try:
            override = connection.execute(
                "SELECT category,subcategory FROM transaction_category_overrides WHERE transaction_id=?",
                (self.transaction_id,),
            ).fetchone()
            merchant_rule = connection.execute(
                "SELECT category FROM merchant_mappings WHERE merchant_normalized='synthetic shop'"
            ).fetchone()[0]
        finally:
            connection.close()
        self.assertEqual(tuple(override), ("Exceptional category", "One purchase"))
        self.assertEqual(merchant_rule, "Original category")

    def test_reimbursement_can_be_updated_and_removed(self) -> None:
        first = save_transaction_adjustment(
            self.database, self.transaction_id, 25, "2030-01-12", "Partial return"
        )
        self.assertEqual(first["personal_amount"], 75)
        updated = save_transaction_adjustment(
            self.database, self.transaction_id, 100, "2030-01-13", "Fully returned"
        )
        self.assertEqual(updated["adjustment_type"], "full_reimbursement")
        self.assertEqual(updated["personal_amount"], 0)

        removed = save_transaction_adjustment(
            self.database, self.transaction_id, 0, "", "", remove=True
        )
        self.assertEqual(removed["personal_amount"], 100)
        connection = connect(self.database)
        try:
            count = connection.execute(
                "SELECT COUNT(*) FROM transaction_spending_adjustments"
            ).fetchone()[0]
        finally:
            connection.close()
        self.assertEqual(count, 0)

    def test_invalid_reimbursement_does_not_create_adjustment(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot exceed"):
            save_transaction_adjustment(
                self.database, self.transaction_id, 101, "2030-01-12", "Invalid"
            )
        connection = connect(self.database)
        try:
            count = connection.execute(
                "SELECT COUNT(*) FROM transaction_spending_adjustments"
            ).fetchone()[0]
        finally:
            connection.close()
        self.assertEqual(count, 0)
