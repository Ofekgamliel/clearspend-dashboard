from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from clearspend.import_engine import ImportDatabase, parse_income_sheets, parse_max


class SyntheticImportContractTests(unittest.TestCase):
    def test_fresh_database_contains_current_core_schema(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = ImportDatabase(Path(directory) / "synthetic.db")
            try:
                tables = {
                    row[0]
                    for row in database.connection.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    )
                }
                triggers = {
                    row[0]
                    for row in database.connection.execute(
                        "SELECT name FROM sqlite_master WHERE type='trigger'"
                    )
                }
            finally:
                database.close()

        self.assertTrue(
            {
                "imports",
                "transactions",
                "merchant_mappings",
                "transaction_category_overrides",
                "transaction_spending_adjustments",
                "income_entries",
                "recurring_profiles",
                "events",
                "event_transactions",
                "observation_reviews",
            }.issubset(tables)
        )
        self.assertIn("apply_merchant_mapping_after_insert", triggers)

    def test_income_parser_preserves_contributors_for_one_household_month(self) -> None:
        entries = parse_income_sheets(
            [
                (
                    "Income",
                    [
                        {"A": "Date", "B": "Name", "C": "Amount"},
                        {"A": "January 2030", "B": "Contributor Alpha", "C": 10000},
                        {"A": "January 2030", "B": "Contributor Beta", "C": 12500},
                    ],
                )
            ]
        )

        self.assertEqual(len(entries), 2)
        self.assertEqual({entry.month for entry in entries}, {"2030-01"})
        self.assertEqual(sum(float(entry.amount) for entry in entries), 22500)

    def test_max_parser_keeps_each_synthetic_transaction_card(self) -> None:
        sheets = [
            (
                "עסקאות במועד החיוב",
                [
                    {"A": "כל המשתמשים (2)"},
                    {"A": "כל הכרטיסים (2)"},
                    {"A": "2030-01-01-2030-01-31"},
                    {
                        "A": "תאריך עסקה",
                        "B": "שם בית העסק",
                        "D": "4 ספרות אחרונות של כרטיס האשראי",
                    },
                    {"A": "05-01-2030", "B": "Synthetic Market", "D": 1, "F": 50, "G": "₪"},
                    {"A": "06-01-2030", "B": "Synthetic Cafe", "D": 22, "F": 25, "G": "₪"},
                ],
            )
        ]

        statement = parse_max(Path("synthetic-multi-card.xlsx"), sheets)

        self.assertEqual(statement.card_last4, "multiple")
        self.assertEqual([item.card_last4 for item in statement.transactions], ["0001", "0022"])
        self.assertTrue(all(item.transaction_key for item in statement.transactions))


if __name__ == "__main__":
    unittest.main()
