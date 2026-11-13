from __future__ import annotations

import unittest

from clearspend.observations.historical_analysis import HistoricalObservationAnalysis
from clearspend.observations.historical_merchant_rules import RegularMerchantHabit
from clearspend.observations.historical_presentation import (
    historical_findings,
    historical_observation_groups,
)
from clearspend.observations.historical_rules import (
    AmountLeftTrend,
    CategoryRoutineShift,
    HistoricalHouseholdMonth,
    PersistentInstallmentBurden,
    RecurringBurdenShift,
    SpendingRoutineShift,
)


PRE = ("2029-10", "2029-11", "2029-12")
POST = ("2030-01", "2030-02", "2030-03")


def empty_analysis(**overrides) -> HistoricalObservationAnalysis:
    values = {
        "amount_left": None,
        "spending_routine": None,
        "recurring_burden": None,
        "installment_burden": None,
        "category_routines": (),
        "newly_regular_merchants": (),
        "merchant_habit_shifts": (),
    }
    values.update(overrides)
    return HistoricalObservationAnalysis(**values)


def regular_merchant(number: int) -> RegularMerchantHabit:
    return RegularMerchantHabit(
        observation_type="MERCHANT HABIT SHIFTED",
        identity=f"merchant-{number}",
        merchant_label=f"Synthetic merchant {number}",
        start_month="2030-01",
        pre_months=PRE,
        establishment_months=POST,
        purchase_count=6,
        purchase_days=6,
        monthly_spending=(200, 200, 200),
        average_monthly_spending=200,
        established_frequency=2,
        prior_active_months=0,
        later_months=0,
        later_active_months=0,
        recent_frequency=2,
        spending_qualified=True,
        frequency_qualified=True,
        buying_more=False,
        still_visible=True,
        score=float(number),
    )


class HistoricalObservationPresentationTests(unittest.TestCase):
    def test_spending_signal_becomes_rich_finding_without_requalification(self) -> None:
        signal = SpendingRoutineShift(
            observation_type="SPENDING ROUTINE SHIFTED",
            start_month="2030-01",
            pre_months=PRE,
            post_months=POST,
            pre_values=(5_000, 5_000, 5_000),
            post_values=(7_000, 7_000, 7_000),
            baseline=5_000,
            post_average=7_000,
            direction=1,
            duration=3,
            active=True,
            score=2_000,
            difference=2_000,
            change_percentage=40,
        )
        finding = historical_findings(empty_analysis(spending_routine=signal))[0]
        self.assertEqual(finding.month, "2030-01")
        self.assertEqual(finding.value, "₪7,000.00")
        self.assertEqual(finding.comparison, "₪5,000.00")
        self.assertIn("+40.0%", finding.result)
        self.assertEqual(len(finding.evidence), 6)
        self.assertEqual(finding.card_summary, "")

    def test_amount_left_growth_labels_explain_both_sides(self) -> None:
        pre_rows = tuple(
            HistoricalHouseholdMonth(month, 10_000, 5_000) for month in PRE
        )
        post_rows = tuple(
            HistoricalHouseholdMonth(month, 10_000, 7_000) for month in POST
        )
        signal = AmountLeftTrend(
            observation_type="AMOUNT LEFT TREND",
            kind="spending_outgrew_income",
            start_month="2030-01",
            pre_months=PRE,
            post_months=POST,
            pre_rows=pre_rows,
            post_rows=post_rows,
            duration=3,
            active=True,
            severity=2,
            score=4_000,
            baseline_income=10_000,
            post_income=10_000,
            baseline_spending=5_000,
            post_spending=7_000,
            income_growth=0,
            spending_growth=0.4,
            growth_gap=0.4,
        )
        finding = historical_findings(empty_analysis(amount_left=signal))[0]
        self.assertEqual(finding.value_label, "Spending growth")
        self.assertEqual(finding.comparison_label, "Income growth")
        self.assertEqual(finding.result_label, "Growth gap")
        self.assertIn("Spending +40.0%", finding.card_comparison_primary)
        self.assertIn("Income +0.0%", finding.card_comparison_primary)

    def test_long_period_groups_keep_established_type_priority(self) -> None:
        category = CategoryRoutineShift(
            observation_type="CATEGORY ROUTINE SHIFTED",
            category="Synthetic category",
            start_month="2030-01",
            pre_months=PRE,
            post_months=POST,
            pre_values=(500, 500, 500),
            post_values=(1_100, 1_100, 1_100),
            baseline=500,
            post_average=1_100,
            direction=1,
            duration=3,
            active=True,
            score=600,
            drivers=("Synthetic merchant",),
        )
        recurring = RecurringBurdenShift(
            observation_type="RECURRING BURDEN SHIFTED",
            start_month="2030-01",
            pre_months=PRE,
            post_months=POST,
            count_baseline=1,
            count_after=3,
            cost_baseline=500,
            cost_after=700,
            count_shift=True,
            cost_shift=True,
            duration=3,
            active=True,
            score=700,
            started=("Synthetic service",),
            ended=(),
            changed=(),
        )
        installment = PersistentInstallmentBurden(
            observation_type="PERSISTENT INSTALLMENT BURDEN",
            start_month="2030-01",
            months=("2030-01", "2030-02", "2030-03", "2030-04", "2030-05", "2030-06"),
            burdens=(1_200,) * 6,
            duration=6,
            active=True,
            average_burden=1_200,
            starts=2,
            endings=2,
            replacements=True,
            score=7_200,
        )
        groups = historical_observation_groups(empty_analysis(
            recurring_burden=recurring,
            installment_burden=installment,
            category_routines=(category,),
        ))
        self.assertEqual(tuple(group.observation_type for group in groups), (
            "RECURRING BURDEN SHIFTED",
            "PERSISTENT INSTALLMENT BURDEN",
            "CATEGORY ROUTINE SHIFTED",
        ))
        self.assertIn("2 starts", groups[1].result)

    def test_merchant_surface_is_limited_to_twelve_strongest_findings(self) -> None:
        merchants = tuple(regular_merchant(number) for number in range(1, 15))
        findings = historical_findings(empty_analysis(
            newly_regular_merchants=merchants,
        ))
        self.assertEqual(len(findings), 12)
        self.assertEqual(findings[0].label, "Synthetic merchant 14")
        self.assertEqual(findings[-1].label, "Synthetic merchant 3")
        group = historical_observation_groups(empty_analysis(
            newly_regular_merchants=merchants,
        ))[0]
        self.assertEqual(group.title, "12 merchants became regular")
        self.assertIn("+10 more", group.merchant_preview)


if __name__ == "__main__":
    unittest.main()
