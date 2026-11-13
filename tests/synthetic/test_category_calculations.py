from __future__ import annotations

import unittest

from clearspend.reporting.categories import (
    with_previous_month_comparison,
    with_spending_shares,
)


class CategoryCalculationTests(unittest.TestCase):
    def test_spending_share_uses_selected_total(self) -> None:
        rows = with_spending_shares(
            [{"category": "Alpha", "amount": 100}, {"category": "Beta", "amount": 200}],
            300,
        )

        self.assertEqual([row["share"] for row in rows], [33.3, 66.7])

    def test_zero_total_has_zero_share(self) -> None:
        rows = with_spending_shares([{"category": "Alpha", "amount": 0}], 0)

        self.assertEqual(rows[0]["share"], 0)

    def test_missing_previous_coverage_is_unavailable(self) -> None:
        rows = with_previous_month_comparison(
            [{"category": "Alpha", "amount": 150}],
            previous_transaction_count=0,
            previous_amounts={},
        )

        self.assertEqual(rows[0]["comparison"], "unavailable")
        self.assertIsNone(rows[0]["change_percent"])

    def test_new_increased_decreased_and_unchanged_categories(self) -> None:
        rows = with_previous_month_comparison(
            [
                {"category": "New", "amount": 40},
                {"category": "Up", "amount": 150},
                {"category": "Down", "amount": 75},
                {"category": "Same", "amount": 100},
            ],
            previous_transaction_count=4,
            previous_amounts={"Up": 100, "Down": 100, "Same": 100},
        )

        by_category = {row["category"]: row for row in rows}
        self.assertEqual(by_category["New"]["comparison"], "new")
        self.assertEqual(by_category["Up"]["change_percent"], 50)
        self.assertEqual(by_category["Up"]["comparison"], "up")
        self.assertEqual(by_category["Down"]["change_percent"], -25)
        self.assertEqual(by_category["Down"]["comparison"], "down")
        self.assertEqual(by_category["Same"]["comparison"], "same")

    def test_calculations_do_not_mutate_query_rows(self) -> None:
        source = {"category": "Alpha", "amount": 100}

        with_spending_shares([source], 100)
        with_previous_month_comparison(
            [source], previous_transaction_count=1, previous_amounts={"Alpha": 50}
        )

        self.assertEqual(source, {"category": "Alpha", "amount": 100})


if __name__ == "__main__":
    unittest.main()
