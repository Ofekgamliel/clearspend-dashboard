from __future__ import annotations

import unittest

from clearspend.observations.monthly_rules import (
    AMOUNT_LEFT_OBSERVATION,
    CATEGORY_SPENDING_OBSERVATION,
    HouseholdMonth,
    MERCHANT_ACTIVITY_OBSERVATION,
    MerchantActivityMonth,
    amount_left_decrease,
    category_spending_increase,
    merchant_activity_change,
)


def household(month: str, income: float = 10_000, spending: float = 5_000) -> HouseholdMonth:
    return HouseholdMonth(month=month, income=income, spending=spending)


class AmountLeftRuleTests(unittest.TestCase):
    def test_overspending_qualifies_even_without_a_large_baseline_drop(self) -> None:
        history = [household(f"2030-0{month}", spending=10_500) for month in range(1, 4)]
        signal = amount_left_decrease(household("2030-04", spending=10_100), history)
        self.assertIsNotNone(signal)
        self.assertEqual(signal.observation_type, AMOUNT_LEFT_OBSERVATION)
        self.assertTrue(signal.overspent)
        self.assertEqual(signal.remaining, -100)

    def test_non_overspending_month_requires_both_decline_thresholds(self) -> None:
        history = [household(f"2030-0{month}") for month in range(1, 4)]
        with self.subTest("amount only"):
            self.assertIsNone(amount_left_decrease(
                household("2030-04", income=8_000, spending=5_000), history,
            ))
        with self.subTest("percentage only"):
            self.assertIsNone(amount_left_decrease(
                household("2030-04", income=5_000, spending=1_000), history,
            ))

    def test_decline_thresholds_are_inclusive_and_evidence_is_preserved(self) -> None:
        history = [household(f"2030-0{month}") for month in range(1, 4)]
        signal = amount_left_decrease(household("2030-04", spending=7_000), history)
        self.assertIsNotNone(signal)
        self.assertEqual(signal.amount_drop, 2_000)
        self.assertEqual(signal.percentage_point_drop, 20)
        self.assertEqual(signal.comparison_months, ("2030-01", "2030-02", "2030-03"))

    def test_requires_exactly_three_prior_months_with_income(self) -> None:
        valid = [household(f"2030-0{month}") for month in range(1, 4)]
        self.assertIsNone(amount_left_decrease(household("2030-04", spending=8_000), valid[:2]))
        self.assertIsNone(amount_left_decrease(
            household("2030-04", spending=8_000),
            [valid[0], household("2030-02", income=0), valid[2]],
        ))
        self.assertIsNone(amount_left_decrease(household("2030-04", income=0), valid))


class CategorySpendingRuleTests(unittest.TestCase):
    def test_requires_spending_in_at_least_two_prior_months(self) -> None:
        self.assertIsNone(category_spending_increase(
            "Synthetic category", 2_000, 10_000, [500, 0, 0],
        ))

    def test_zero_covered_month_remains_in_three_month_median(self) -> None:
        signal = category_spending_increase(
            "Synthetic category", 2_000, 10_000, [0, 500, 600],
        )
        self.assertIsNotNone(signal)
        self.assertEqual(signal.baseline, 500)
        self.assertEqual(signal.active_history_months, 2)
        self.assertEqual(signal.previous_amounts, (0, 500, 600))

    def test_ratio_increase_and_share_must_all_qualify(self) -> None:
        cases = (
            (1_900, 10_000, [1_000, 1_000, 1_000]),
            (1_099, 10_000, [100, 100, 100]),
            (2_000, 40_000, [500, 500, 500]),
        )
        for current, total, history in cases:
            with self.subTest(current=current, total=total, history=history):
                self.assertIsNone(category_spending_increase(
                    "Synthetic category", current, total, history,
                ))

    def test_all_thresholds_are_inclusive_and_signal_fields_are_complete(self) -> None:
        signal = category_spending_increase(
            "Synthetic category", 2_000, 20_000, [1_000, 1_000, 1_000],
        )
        self.assertIsNotNone(signal)
        self.assertEqual(signal.observation_type, CATEGORY_SPENDING_OBSERVATION)
        self.assertEqual(signal.increase, 1_000)
        self.assertEqual(signal.ratio, 2)
        self.assertEqual(signal.routine_share, 0.1)
        self.assertIsNone(category_spending_increase(
            "Synthetic category", 2_000, 0, [1_000, 1_000, 1_000],
        ))


class MerchantActivityRuleTests(unittest.TestCase):
    def test_requires_three_comparison_slots_and_positive_current_activity(self) -> None:
        history = [
            MerchantActivityMonth("2030-01", 3, 300),
            MerchantActivityMonth("2030-02", 3, 300),
            MerchantActivityMonth("2030-03", 0, 0),
        ]
        current = MerchantActivityMonth("2030-04", 6, 600)
        self.assertIsNone(merchant_activity_change(current, history[:2]))
        self.assertIsNone(merchant_activity_change(
            MerchantActivityMonth("2030-04", 0, 0), history,
        ))

    def test_requires_two_active_months_and_five_historical_purchases(self) -> None:
        current = MerchantActivityMonth("2030-04", 8, 800)
        self.assertIsNone(merchant_activity_change(current, [
            MerchantActivityMonth("2030-01", 5, 500),
            MerchantActivityMonth("2030-02", 0, 0),
            MerchantActivityMonth("2030-03", 0, 0),
        ]))
        self.assertIsNone(merchant_activity_change(current, [
            MerchantActivityMonth("2030-01", 2, 200),
            MerchantActivityMonth("2030-02", 2, 200),
            MerchantActivityMonth("2030-03", 0, 0),
        ]))

    def test_active_month_medians_exclude_covered_zero_months(self) -> None:
        signal = merchant_activity_change(
            MerchantActivityMonth("2030-04", 6, 700),
            [
                MerchantActivityMonth("2030-01", 3, 400),
                MerchantActivityMonth("2030-02", 2, 400),
                MerchantActivityMonth("2030-03", 0, 0),
            ],
        )
        self.assertIsNotNone(signal)
        self.assertEqual(signal.baseline_total, 400)
        self.assertEqual(signal.baseline_count, 2.5)
        self.assertEqual(len(signal.active_history), 2)
        self.assertEqual(signal.history_purchase_count, 5)

    def test_spending_path_requires_ratio_and_absolute_increase(self) -> None:
        def result(current_total: float, baseline: float):
            return merchant_activity_change(
                MerchantActivityMonth("2030-04", 3, current_total),
                [
                    MerchantActivityMonth("2030-01", 3, baseline),
                    MerchantActivityMonth("2030-02", 3, baseline),
                    MerchantActivityMonth("2030-03", 0, 0),
                ],
            )

        self.assertIsNotNone(result(700, 400))  # ratio boundary
        self.assertIsNotNone(result(400, 200))  # increase boundary
        self.assertIsNone(result(699, 400))
        self.assertIsNone(result(399, 200))

    def test_count_path_requires_ratio_and_three_additional_purchases(self) -> None:
        qualifies = merchant_activity_change(
            MerchantActivityMonth("2030-04", 6, 300),
            [
                MerchantActivityMonth("2030-01", 3, 300),
                MerchantActivityMonth("2030-02", 3, 300),
                MerchantActivityMonth("2030-03", 0, 0),
            ],
        )
        self.assertIsNotNone(qualifies)
        self.assertFalse(qualifies.spending_changed)
        self.assertTrue(qualifies.purchase_count_changed)

        for current_count, historical_counts in ((5, (1, 4)), (7, (4, 4))):
            with self.subTest(current_count=current_count, history=historical_counts):
                self.assertIsNone(merchant_activity_change(
                    MerchantActivityMonth("2030-04", current_count, 300),
                    [
                        MerchantActivityMonth("2030-01", historical_counts[0], 300),
                        MerchantActivityMonth("2030-02", historical_counts[1], 300),
                        MerchantActivityMonth("2030-03", 0, 0),
                    ],
                ))

    def test_signal_preserves_both_change_paths_when_both_qualify(self) -> None:
        signal = merchant_activity_change(
            MerchantActivityMonth("2030-04", 6, 800),
            [
                MerchantActivityMonth("2030-01", 3, 400),
                MerchantActivityMonth("2030-02", 3, 400),
                MerchantActivityMonth("2030-03", 0, 0),
            ],
        )
        self.assertIsNotNone(signal)
        self.assertEqual(signal.observation_type, MERCHANT_ACTIVITY_OBSERVATION)
        self.assertTrue(signal.spending_changed)
        self.assertTrue(signal.purchase_count_changed)
        self.assertEqual(signal.spending_ratio, 2)
        self.assertEqual(signal.purchase_count_ratio, 2)


if __name__ == "__main__":
    unittest.main()
