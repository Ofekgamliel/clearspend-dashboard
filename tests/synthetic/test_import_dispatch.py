from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch, sentinel

from clearspend.imports.dispatch import parse_statement, parse_xlsx


class ImportDispatchTests(unittest.TestCase):
    @patch("clearspend.imports.dispatch.parse_isracard")
    @patch("clearspend.imports.dispatch.read_xlsx")
    def test_xlsx_isracard_markers_select_isracard_adapter(self, read, parse) -> None:
        sheets = [("Synthetic", [{"A": "תאריך רכישה", "B": "ישראכרט"}])]
        read.return_value = sheets
        parse.return_value = sentinel.statement
        path = Path("synthetic.xlsx")

        result = parse_xlsx(path)

        self.assertIs(result, sentinel.statement)
        parse.assert_called_once_with(path, sheets)

    @patch("clearspend.imports.dispatch.parse_max")
    @patch("clearspend.imports.dispatch.read_xlsx")
    def test_xlsx_max_markers_select_max_adapter(self, read, parse) -> None:
        sheets = [
            (
                "Synthetic",
                [{"A": "4 ספרות אחרונות של כרטיס האשראי"}],
            )
        ]
        read.return_value = sheets
        parse.return_value = sentinel.statement
        path = Path("synthetic.xlsx")

        result = parse_xlsx(path)

        self.assertIs(result, sentinel.statement)
        parse.assert_called_once_with(path, sheets)

    @patch("clearspend.imports.dispatch.read_xlsx")
    def test_unmatched_xlsx_profile_is_rejected(self, read) -> None:
        read.return_value = [("Synthetic", [{"A": "Unknown format"}])]

        with self.assertRaisesRegex(ValueError, "No supported statement profile"):
            parse_xlsx(Path("synthetic.xlsx"))

    @patch("clearspend.imports.dispatch.parse_leumi_pdf")
    @patch("clearspend.imports.dispatch.parse_xlsx")
    def test_statement_extension_selects_parser_and_rejects_unknown(
        self,
        parse_workbook,
        parse_pdf,
    ) -> None:
        parse_workbook.return_value = sentinel.workbook
        parse_pdf.return_value = sentinel.pdf

        self.assertIs(parse_statement(Path("synthetic.XLSX")), sentinel.workbook)
        self.assertIs(parse_statement(Path("synthetic.PDF")), sentinel.pdf)
        with self.assertRaisesRegex(ValueError, "Unsupported statement format"):
            parse_statement(Path("synthetic.csv"))


if __name__ == "__main__":
    unittest.main()
