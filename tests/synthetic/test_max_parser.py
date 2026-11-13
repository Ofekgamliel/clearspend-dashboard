from __future__ import annotations

import unittest
from pathlib import Path

from clearspend.imports.max import parse_max


class MaxParserTests(unittest.TestCase):
    def test_single_card_rows_preserve_provider_fields_and_total(self) -> None:
        sheets = [
            (
                "עסקאות במועד החיוב",
                [
                    {"A": "Synthetic user"},
                    {"A": "0001-Synthetic max"},
                    {"A": "2030-04-01-2030-04-30"},
                    {
                        "A": "10-04-2030",
                        "B": "Synthetic Store",
                        "C": "Synthetic Category",
                        "E": "חיוב עסקות מיידי",
                        "F": "125.50",
                        "G": "ILS",
                        "H": "30.00",
                        "I": "USD",
                        "J": "15-04-2030",
                        "K": "תשלום 2 מתוך 4",
                        "O": "Synthetic Method",
                        "P": "4.18",
                    },
                    {"A": "סך הכל"},
                    {"A": "1,234.56 ILS"},
                ],
            )
        ]

        statement = parse_max(Path("synthetic.xlsx"), sheets)

        self.assertEqual(statement.card_last4, "0001")
        self.assertEqual(statement.product_name, "Synthetic max")
        self.assertEqual(statement.date_range, "2030-04-01-2030-04-30")
        self.assertEqual(statement.official_total, "1234.56")
        self.assertEqual(len(statement.transactions), 1)
        item = statement.transactions[0]
        self.assertEqual(item.source_sheet, "עסקאות במועד החיוב:immediate")
        self.assertEqual((item.billing_month, item.billing_month_source), ("2030-04", "provider"))
        self.assertEqual((item.installment_number, item.installment_total), (2, 4))
        self.assertEqual(item.provider_category, "Synthetic Category")
        self.assertEqual(item.execution_method, "Synthetic Method")
        self.assertEqual(item.exchange_rate, "4.18")
        self.assertTrue(item.transaction_key)

    def test_workbook_without_transaction_sheets_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "no transaction sheets"):
            parse_max(Path("synthetic.xlsx"), [("Export Summary", [])])


if __name__ == "__main__":
    unittest.main()
