from __future__ import annotations

import sqlite3
import unittest

from clearspend.reporting.personal_spending import (
    personal_spending_amount,
    personal_spending_sql,
    review_reimbursement,
)


class PersonalSpendingTests(unittest.TestCase):
    def test_personal_amount_excludes_refunds_and_reviewed_reimbursement(self) -> None:
        self.assertEqual(personal_spending_amount(-50), 0)
        self.assertEqual(personal_spending_amount(100), 100)
        self.assertEqual(personal_spending_amount(100, 75), 25)
        self.assertEqual(personal_spending_amount(100, 120), 0)

    def test_reviewed_reimbursement_classifies_partial_and_full(self) -> None:
        partial = review_reimbursement(100, 75)
        full = review_reimbursement(100, 100)

        self.assertEqual(partial.adjustment_type, "partial_reimbursement")
        self.assertEqual(partial.personal_amount, 25)
        self.assertEqual(full.adjustment_type, "full_reimbursement")
        self.assertEqual(full.personal_amount, 0)

    def test_reviewed_reimbursement_rejects_invalid_amounts(self) -> None:
        with self.assertRaisesRegex(ValueError, "positive card charges"):
            review_reimbursement(0, 10)
        with self.assertRaisesRegex(ValueError, "greater than zero"):
            review_reimbursement(100, 0)
        with self.assertRaisesRegex(ValueError, "cannot exceed"):
            review_reimbursement(100, 101)
        with self.assertRaisesRegex(ValueError, "greater than zero"):
            review_reimbursement(100, float("nan"))

    def test_sql_expression_matches_pure_rule(self) -> None:
        connection = sqlite3.connect(":memory:")
        try:
            connection.execute(
                "CREATE TABLE transactions(id INTEGER PRIMARY KEY,charged_amount TEXT)"
            )
            connection.execute(
                """CREATE TABLE transaction_spending_adjustments(
                transaction_id INTEGER PRIMARY KEY,reimbursed_amount TEXT)"""
            )
            cases = [(1, "100.00", None), (2, "100.00", "75.00"), (3, "-50.00", None)]
            for transaction_id, charge, reimbursement in cases:
                connection.execute(
                    "INSERT INTO transactions(id,charged_amount) VALUES(?,?)",
                    (transaction_id, charge),
                )
                if reimbursement is not None:
                    connection.execute(
                        """INSERT INTO transaction_spending_adjustments(
                        transaction_id,reimbursed_amount) VALUES(?,?)""",
                        (transaction_id, reimbursement),
                    )
            rows = connection.execute(
                f"SELECT t.id,{personal_spending_sql()} amount FROM transactions t ORDER BY t.id"
            ).fetchall()
        finally:
            connection.close()

        expected = [
            personal_spending_amount(float(charge), float(reimbursement or 0))
            for _transaction_id, charge, reimbursement in cases
        ]
        self.assertEqual([row[1] for row in rows], expected)


if __name__ == "__main__":
    unittest.main()
