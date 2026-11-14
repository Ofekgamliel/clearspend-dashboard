from __future__ import annotations

import unittest

from clearspend.observations.historical_analysis import (
    HistoricalObservationDataset,
    analyze_historical_observations,
)
from clearspend.observations.historical_merchant_rules import (
    HistoricalMerchantTransaction,
)
from clearspend.observations.historical_rules import (
    HistoricalCategoryTransaction,
    HistoricalHouseholdMonth,
    HistoricalInstallmentMonth,
    HistoricalInstallmentPlan,
    HistoricalRecurringMonth,
    HistoricalRecurringSeries,
    HistoricalTransaction,
)


BASELINE = ("2029-07", "2029-08", "2029-09", "2029-10", "2029-11", "2029-12")
TARGET = ("2030-01", "2030-02", "2030-03", "2030-04", "2030-05", "2030-06")
COVERAGE = (*BASELINE, *TARGET)


class HistoricalObservationAnalysisTests(unittest.TestCase):
    def test_empty_dataset_returns_no_signals(self) -> None:
        analysis = analyze_historical_observations(
            HistoricalObservationDataset(TARGET, COVERAGE),
        )
        self.assertEqual(analysis.signals, ())

    def test_coordinator_combines_household_spending_and_category_rules(self) -> None:
        routine = tuple(
            HistoricalTransaction(month, 5_000 if month in BASELINE else 7_000)
            for month in COVERAGE
        )
        category = tuple(
            HistoricalCategoryTransaction(
                month,
                "Synthetic category",
                "Synthetic merchant",
                1_000 if month in BASELINE else 1_600,
            )
            for month in COVERAGE
        )
        household = {
            month: HistoricalHouseholdMonth(
                month,
                10_000,
                5_000 if month in BASELINE else 7_000,
            )
            for month in COVERAGE
        }
        analysis = analyze_historical_observations(HistoricalObservationDataset(
            TARGET,
            COVERAGE,
            routine_transactions=routine,
            category_transactions=category,
            household_history=household,
        ))
        self.assertEqual(analysis.amount_left.kind, "spending_outgrew_income")
        self.assertEqual(analysis.spending_routine.start_month, "2030-01")
        self.assertEqual(
            tuple(item.category for item in analysis.category_routines),
            ("Synthetic category",),
        )
        self.assertEqual(
            tuple(signal.observation_type for signal in analysis.signals[:3]),
            (
                "AMOUNT LEFT TREND",
                "SPENDING ROUTINE SHIFTED",
                "CATEGORY ROUTINE SHIFTED",
            ),
        )

    def test_recurring_and_installment_families_share_one_result(self) -> None:
        recurring = {}
        installments = {}
        for month in COVERAGE:
            recent = month in TARGET
            recurring[month] = HistoricalRecurringMonth(
                month,
                (HistoricalRecurringSeries(
                    "synthetic-series",
                    700 if recent else 500,
                    "Monthly",
                    "active",
                    "Synthetic service",
                ),),
                active_series_count=3 if recent else 1,
            )
            installments[month] = HistoricalInstallmentMonth(
                month,
                1_200 if recent else 0,
                (HistoricalInstallmentPlan(
                    plan_id="synthetic-plan",
                    display_name="Synthetic plan",
                ),) if recent else (),
            )
        analysis = analyze_historical_observations(HistoricalObservationDataset(
            TARGET,
            COVERAGE,
            recurring_history=recurring,
            installment_history=installments,
        ))
        self.assertTrue(analysis.recurring_burden.cost_shift)
        self.assertTrue(analysis.recurring_burden.count_shift)
        self.assertEqual(analysis.installment_burden.duration, 6)
        self.assertEqual(
            tuple(signal.observation_type for signal in analysis.signals),
            ("RECURRING BURDEN SHIFTED", "PERSISTENT INSTALLMENT BURDEN"),
        )

    def test_purchase_date_merchant_habits_remain_separate_from_reporting_month(self) -> None:
        merchant_rows = tuple(
            HistoricalMerchantTransaction(
                "synthetic-id",
                "Synthetic café",
                "synthetic cafe branch",
                f"{month}-{day:02d}",
                100,
                "Restaurants",
            )
            for month in TARGET[:3]
            for day in (2, 15)
        )
        analysis = analyze_historical_observations(HistoricalObservationDataset(
            TARGET,
            COVERAGE,
            merchant_transactions=merchant_rows,
        ))
        self.assertEqual(len(analysis.newly_regular_merchants), 1)
        self.assertEqual(
            analysis.newly_regular_merchants[0].merchant_label,
            "Synthetic café",
        )
        self.assertEqual(analysis.merchant_habit_shifts, ())

    def test_partial_month_is_forwarded_to_every_historical_family(self) -> None:
        selected = (*TARGET, "2030-07")
        routine = tuple(
            HistoricalTransaction(month, 5_000 if month in BASELINE else 7_000)
            for month in (*COVERAGE, "2030-07")
        )
        analysis = analyze_historical_observations(HistoricalObservationDataset(
            selected,
            (*COVERAGE, "2030-07"),
            routine_transactions=routine,
            partial_month="2030-07",
        ))
        self.assertEqual(analysis.spending_routine.duration, 6)
        self.assertTrue(analysis.spending_routine.active)


if __name__ == "__main__":
    unittest.main()
