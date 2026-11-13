from __future__ import annotations

import unittest

from clearspend.imports.domain import (
    IncomeEntry,
    ParsedStatement,
    Transaction,
    amount,
    assign_occurrences,
    clean_text,
    normalize_merchant,
    parse_date,
    parse_installment,
    parse_statement_month,
)


def transaction(merchant: str = "Synthetic Store") -> Transaction:
    return Transaction(
        provider="synthetic",
        card_last4="0001",
        source_sheet="synthetic-sheet",
        transaction_date="2030-04-10",
        billing_date=None,
        merchant_raw=merchant,
        merchant_normalized=normalize_merchant(merchant),
        charged_amount="25.00",
        charged_currency="ILS",
        original_amount="25.00",
        original_currency="ILS",
        billing_month="2030-04",
        billing_month_source="statement",
        source_payload={"invented": True},
    )


class ImportDomainTests(unittest.TestCase):
    def test_text_and_merchant_normalization_are_stable(self) -> None:
        self.assertEqual(clean_text("  Synthetic\u202a   Store  "), "Synthetic Store")
        self.assertEqual(normalize_merchant("SYNTHETIC-Store!"), "synthetic store")
        self.assertIsNone(clean_text("   "))

    def test_amount_date_statement_month_and_installment_parsing(self) -> None:
        self.assertEqual(amount("1,234.5"), "1234.50")
        self.assertIsNone(amount("not-an-amount"))
        self.assertEqual(parse_date("10-04-2030"), "2030-04-10")
        self.assertEqual(parse_statement_month("April 2030"), "2030-04")
        self.assertEqual(
            parse_statement_month(None, "synthetic_04_2030.xlsx"),
            "2030-04",
        )
        self.assertEqual(parse_installment("תשלום 2 מתוך 6"), (2, 6))

    def test_occurrences_distinguish_otherwise_identical_transactions(self) -> None:
        first = transaction()
        second = transaction()

        assign_occurrences([first, second])

        self.assertEqual(first.base_key, second.base_key)
        self.assertEqual((first.occurrence, second.occurrence), (1, 2))
        self.assertNotEqual(first.transaction_key, second.transaction_key)

    def test_statement_semantic_hash_does_not_depend_on_row_order(self) -> None:
        first = transaction("Synthetic Alpha")
        second = transaction("Synthetic Beta")
        assign_occurrences([first, second])

        forward = ParsedStatement("synthetic", "0001", None, None, [first, second])
        reverse = ParsedStatement("synthetic", "0001", None, None, [second, first])

        self.assertEqual(forward.semantic_hash, reverse.semantic_hash)

    def test_income_entry_identity_includes_occurrence(self) -> None:
        first = IncomeEntry("2030-04", "Synthetic Income", "1000.00", occurrence=1)
        second = IncomeEntry("2030-04", "Synthetic Income", "1000.00", occurrence=2)
        first.establish_identity()
        second.establish_identity()

        self.assertNotEqual(first.entry_key, second.entry_key)


if __name__ == "__main__":
    unittest.main()
