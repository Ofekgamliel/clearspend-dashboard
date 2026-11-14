from __future__ import annotations

import unittest

from clearspend.reporting.calculations import (
    calculate_income_balance,
    calculate_monthly_averages,
)


class ReportingCalculationTests(unittest.TestCase):
    def test_income_balance_accounts_for_refunds_and_reimbursements(self) -> None:
        balance = calculate_income_balance(
            income=10000,
            personal_positive_spending=4000,
            gross_charges=4750,
            refunds=500,
        )

        self.assertEqual(balance.income, 10000)
        self.assertEqual(balance.spending, 3500)
        self.assertEqual(balance.charges, 4750)
        self.assertEqual(balance.refunds, 500)
        self.assertEqual(balance.remaining, 6500)
        self.assertEqual(balance.spent_percentage, 35.0)
        self.assertEqual(balance.remaining_percentage, 65.0)

    def test_zero_income_does_not_create_misleading_percentages(self) -> None:
        balance = calculate_income_balance(
            income=0,
            personal_positive_spending=250,
            gross_charges=250,
            refunds=0,
        )

        self.assertEqual(balance.remaining, -250)
        self.assertIsNone(balance.spent_percentage)
        self.assertIsNone(balance.remaining_percentage)

    def test_spending_average_uses_only_months_with_spending_records(self) -> None:
        averages = calculate_monthly_averages(
            {"2030-01": 100, "2030-03": 300},
            {},
            current_month="2030-03",
        )

        self.assertEqual(averages.spending, 200)
        self.assertEqual(averages.spending_months, 2)
        self.assertIsNone(averages.amount_left)
        self.assertTrue(averages.current_month_partial)

    def test_amount_left_uses_income_months_and_zero_for_missing_spending(self) -> None:
        averages = calculate_monthly_averages(
            {"2030-01": 400, "2030-03": 300},
            {"2030-01": 1000, "2030-02": 1000},
            current_month="2030-04",
        )

        self.assertEqual(averages.amount_left, 800)
        self.assertEqual(averages.amount_left_months, 2)
        self.assertEqual(averages.start_month, "2030-01")
        self.assertEqual(averages.end_month, "2030-03")
        self.assertFalse(averages.current_month_partial)


if __name__ == "__main__":
    unittest.main()
