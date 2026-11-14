from __future__ import annotations

import unittest
from pathlib import Path

from clearspend.imports.leumi import parse_leumi_text


class LeumiParserTests(unittest.TestCase):
    def test_extracted_text_produces_canonical_transactions(self) -> None:
        text = "\n".join(
            [
                "0001 לאומי מסטרקארד",
                "2030 אפריל לתקופה",
                "10.04.3012:30Synthetic Store 30.00עסקה רגילה 25.00",
                "11/04/30Synthetic Cafe עסקה רגילה 10.00",
            ]
        )

        statement = parse_leumi_text(Path("synthetic.pdf"), text)

        self.assertEqual(statement.provider, "isracard")
        self.assertEqual(statement.card_last4, "0001")
        self.assertEqual(statement.date_range, "2030 אפריל")
        self.assertEqual(len(statement.transactions), 2)
        first, second = statement.transactions
        self.assertEqual(first.merchant_raw, "Synthetic Store")
        self.assertEqual(first.transaction_date, "2030-04-10")
        self.assertEqual(first.original_amount, "30.00")
        self.assertEqual(first.charged_amount, "25.00")
        self.assertEqual(first.notes, "time 12:30")
        self.assertEqual((first.billing_month, first.billing_month_source), ("2030-04", "statement"))
        self.assertEqual(second.original_amount, "10.00")
        self.assertTrue(all(item.transaction_key for item in statement.transactions))

    def test_missing_supported_card_suffix_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "card suffix"):
            parse_leumi_text(Path("synthetic.pdf"), "No supported card")

    def test_statement_without_transaction_rows_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "No transaction rows"):
            parse_leumi_text(
                Path("synthetic.pdf"),
                "0001 לאומי מסטרקארד\n2030 אפריל לתקופה",
            )


if __name__ == "__main__":
    unittest.main()
