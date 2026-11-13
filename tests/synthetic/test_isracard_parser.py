from __future__ import annotations

import unittest
from pathlib import Path

from clearspend.imports.isracard import parse_isracard


class IsracardParserTests(unittest.TestCase):
    def test_monthly_and_outside_cycle_rows_keep_distinct_reporting_rules(self) -> None:
        sheets = [
            (
                "Synthetic transactions",
                [
                    {"C": "April 2030"},
                    {"A": "Synthetic Card - 0001"},
                    {"A": "נכונים לתאריך 15/04/2030"},
                    {"B": 'סה"כ לחיוב החודש בכרטיס', "E": "125.50"},
                    {
                        "A": "10.03.30",
                        "B": "Synthetic Monthly Store",
                        "C": "75.50",
                        "D": "ILS",
                        "E": "75.50",
                        "F": "ILS",
                        "G": "voucher-1",
                        "H": "תשלום 2 מתוך 3",
                    },
                    {"A": "עסקאות בחיוב מחוץ למועד"},
                    {
                        "A": "12.04.30",
                        "B": "Synthetic Immediate Store",
                        "C": "50.00",
                        "D": "ILS",
                        "E": "50.00",
                        "F": "ILS",
                    },
                ],
            )
        ]

        statement = parse_isracard(Path("synthetic_04_2030.xlsx"), sheets)

        self.assertEqual(statement.card_last4, "0001")
        self.assertEqual(statement.product_name, "Synthetic Card")
        self.assertEqual(statement.official_total, "125.50")
        self.assertEqual(statement.statement_as_of_date, "2030-04-15")
        self.assertEqual(len(statement.transactions), 2)
        monthly, immediate = statement.transactions
        self.assertEqual(
            (monthly.billing_month, monthly.billing_month_source),
            ("2030-04", "statement"),
        )
        self.assertEqual(
            (monthly.installment_number, monthly.installment_total),
            (2, 3),
        )
        self.assertEqual(monthly.voucher_number, "voucher-1")
        self.assertEqual(monthly.source_sheet, "Synthetic transactions:monthly")
        self.assertEqual(
            (immediate.billing_month, immediate.billing_month_source),
            ("2030-04", "purchase_date"),
        )
        self.assertEqual(immediate.source_sheet, "Synthetic transactions:immediate")
        self.assertTrue(all(item.transaction_key for item in statement.transactions))

    def test_missing_card_suffix_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "card suffix"):
            parse_isracard(
                Path("synthetic.xlsx"),
                [("Synthetic", [{"C": "April 2030"}, {"A": "No suffix"}])],
            )


if __name__ == "__main__":
    unittest.main()
