from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from clearspend.imports.income import (
    is_income_xlsx,
    parse_income_month,
    parse_income_sheets,
)


class IncomeParserTests(unittest.TestCase):
    def test_month_parser_accepts_supported_formats(self) -> None:
        self.assertEqual(parse_income_month("April 2030"), "2030-04")
        self.assertEqual(parse_income_month("2030-04-15"), "2030-04")
        self.assertIsNone(parse_income_month("not a month"))

    def test_duplicate_rows_receive_distinct_entry_identities(self) -> None:
        rows = [
            {"A": "Date", "B": "Name", "C": "Amount"},
            {"A": "April 2030", "B": "Synthetic Income", "C": 1000},
            {"A": "April 2030", "B": "Synthetic Income", "C": 1000},
        ]

        entries = parse_income_sheets([("Synthetic", rows)])

        self.assertEqual([entry.occurrence for entry in entries], [1, 2])
        self.assertNotEqual(entries[0].entry_key, entries[1].entry_key)

    def test_missing_income_columns_or_valid_rows_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "Date, Name, and Amount"):
            parse_income_sheets([("Synthetic", [{"A": "Unrelated"}])])

    @patch("clearspend.imports.income.parse_income_xlsx")
    def test_detection_checks_extension_and_parser_result(self, parse) -> None:
        self.assertFalse(is_income_xlsx(Path("synthetic.pdf")))
        parse.assert_not_called()

        parse.return_value = []
        self.assertTrue(is_income_xlsx(Path("synthetic.xlsx")))

        parse.side_effect = ValueError("not income")
        self.assertFalse(is_income_xlsx(Path("statement.xlsx")))


if __name__ == "__main__":
    unittest.main()
