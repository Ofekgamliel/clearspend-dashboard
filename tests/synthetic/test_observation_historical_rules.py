from __future__ import annotations

import unittest

from clearspend.observations.historical_rules import (
    AMOUNT_LEFT_TREND,
    CATEGORY_ROUTINE_SHIFTED,
    PERSISTENT_INSTALLMENT_BURDEN,
    RECURRING_BURDEN_SHIFTED,
    SPENDING_ROUTINE_SHIFTED,
    HistoricalCategoryTransaction,
    HistoricalHouseholdMonth,
    HistoricalInstallmentMonth,
    HistoricalInstallmentPlan,
    HistoricalRecurringMonth,
    HistoricalRecurringSeries,
    HistoricalTransaction,
    category_routine_shifts,
    candidate_change_windows,
    routine_category_totals,
    routine_spending_totals,
    amount_left_trend,
    persistent_installment_burden,
    recurring_burden_shift,
    spending_routine_shift,
)


PRE_MONTHS = ("2029-07", "2029-08", "2029-09", "2029-10", "2029-11", "2029-12")
SELECTED_MONTHS = ("2030-01", "2030-02", "2030-03")


def totals(post_values: tuple[float, ...], baseline: float = 5_000) -> dict[str, float]:
    return {
        **{month: baseline for month in PRE_MONTHS},
        **dict(zip(SELECTED_MONTHS, post_values)),
    }


class HistoricalObservationRuleTests(unittest.TestCase):
    def test_routine_totals_exclude_events_refunds_and_uncovered_months(self) -> None:
        result = routine_spending_totals(
            ("2030-01", "2030-02"),
            [
                HistoricalTransaction("2030-01", 100),
                HistoricalTransaction("2030-01", 50, event_id=0),
                HistoricalTransaction("2030-01", -25),
                HistoricalTransaction("2030-01", 500, event_id=7),
                HistoricalTransaction("2030-03", 900),
            ],
        )
        self.assertEqual(result, {"2030-01": 150, "2030-02": 0})

    def test_windows_require_three_prior_and_three_selected_months(self) -> None:
        self.assertEqual(candidate_change_windows(SELECTED_MONTHS[:2], PRE_MONTHS), ())
        self.assertEqual(candidate_change_windows(SELECTED_MONTHS, PRE_MONTHS[:2]), ())
        window = candidate_change_windows(SELECTED_MONTHS, PRE_MONTHS)[0]
        self.assertEqual(window.pre_months, PRE_MONTHS)
        self.assertEqual(window.post_months, SELECTED_MONTHS)

    def test_one_isolated_spike_does_not_establish_a_shift(self) -> None:
        self.assertIsNone(spending_routine_shift(
            SELECTED_MONTHS, totals((5_100, 10_000, 5_100)),
        ))

    def test_all_three_post_months_must_remain_on_the_same_side(self) -> None:
        self.assertIsNone(spending_routine_shift(
            SELECTED_MONTHS, totals((6_000, 6_000, 5_000)),
        ))

    def test_higher_thresholds_are_inclusive(self) -> None:
        signal = spending_routine_shift(
            SELECTED_MONTHS, totals((6_000, 6_000, 5_001)),
        )
        self.assertIsNotNone(signal)
        self.assertEqual(signal.observation_type, SPENDING_ROUTINE_SHIFTED)
        self.assertEqual(signal.start_month, "2030-01")
        self.assertTrue(signal.higher)
        self.assertEqual(signal.baseline, 5_000)
        self.assertEqual(signal.post_values, (6_000, 6_000, 5_001))

    def test_lower_thresholds_are_inclusive(self) -> None:
        signal = spending_routine_shift(
            SELECTED_MONTHS, totals((4_000, 4_000, 4_999)),
        )
        self.assertIsNotNone(signal)
        self.assertFalse(signal.higher)
        self.assertLess(signal.difference, 0)
        self.assertLess(signal.change_percentage, 0)

    def test_longer_candidate_wins_and_lifecycle_stops_at_baseline(self) -> None:
        selected = ("2030-01", "2030-02", "2030-03", "2030-04", "2030-05", "2030-06")
        amounts = {
            **{month: 5_000 for month in PRE_MONTHS},
            "2030-01": 6_000,
            "2030-02": 6_000,
            "2030-03": 6_000,
            "2030-04": 5_500,
            "2030-05": 5_000,
            "2030-06": 5_000,
        }
        signal = spending_routine_shift(selected, amounts)
        self.assertEqual(signal.start_month, "2030-01")
        self.assertEqual(signal.duration, 4)
        self.assertFalse(signal.active)

    def test_partial_month_is_removed_before_active_status_is_calculated(self) -> None:
        selected = (*SELECTED_MONTHS, "2030-04")
        amounts = {**totals((6_000, 6_000, 5_500)), "2030-04": 1_000}
        with_partial = spending_routine_shift(
            selected, amounts, partial_month="2030-04",
        )
        without_partial = spending_routine_shift(selected, amounts)
        self.assertTrue(with_partial.active)
        self.assertFalse(without_partial.active)


class AmountLeftTrendRuleTests(unittest.TestCase):
    def history(self, *, income: float = 10_000, spending: float = 5_000):
        return {
            month: HistoricalHouseholdMonth(month, income, spending)
            for month in PRE_MONTHS
        }

    def test_hidden_income_suppresses_the_entire_observation(self) -> None:
        rows = self.history()
        rows.update({
            month: HistoricalHouseholdMonth(month, 10_000, 12_000)
            for month in SELECTED_MONTHS
        })
        self.assertIsNone(amount_left_trend(
            SELECTED_MONTHS, rows, rows, income_visible=False,
        ))

    def test_requires_three_valid_baseline_and_post_income_months(self) -> None:
        rows = self.history()
        rows["2029-07"] = HistoricalHouseholdMonth("2029-07", 0, 0)
        rows["2029-08"] = HistoricalHouseholdMonth("2029-08", 0, 0)
        rows["2029-09"] = HistoricalHouseholdMonth("2029-09", 0, 0)
        rows["2029-10"] = HistoricalHouseholdMonth("2029-10", 0, 0)
        rows.update({
            month: HistoricalHouseholdMonth(month, 10_000, 12_000)
            for month in SELECTED_MONTHS
        })
        self.assertIsNone(amount_left_trend(SELECTED_MONTHS, rows, rows))
        rows = self.history()
        rows.update({
            "2030-01": HistoricalHouseholdMonth("2030-01", 10_000, 12_000),
            "2030-02": HistoricalHouseholdMonth("2030-02", 0, 12_000),
            "2030-03": HistoricalHouseholdMonth("2030-03", 10_000, 12_000),
        })
        self.assertIsNone(amount_left_trend(SELECTED_MONTHS, rows, rows))

    def test_repeated_overspending_has_highest_severity(self) -> None:
        rows = self.history()
        rows.update({
            "2030-01": HistoricalHouseholdMonth("2030-01", 10_000, 11_000),
            "2030-02": HistoricalHouseholdMonth("2030-02", 10_000, 12_000),
            "2030-03": HistoricalHouseholdMonth("2030-03", 10_000, 9_000),
        })
        signal = amount_left_trend(SELECTED_MONTHS, rows, rows)
        self.assertEqual(signal.observation_type, AMOUNT_LEFT_TREND)
        self.assertEqual(signal.kind, "repeated_overspending")
        self.assertEqual(signal.severity, 3)
        self.assertEqual(signal.overspent_months, 2)
        self.assertEqual(signal.average_shortfall, 1_500)

    def test_one_overspent_month_does_not_use_repeated_overspending(self) -> None:
        rows = self.history()
        rows.update({
            "2030-01": HistoricalHouseholdMonth("2030-01", 10_000, 10_100),
            "2030-02": HistoricalHouseholdMonth("2030-02", 10_000, 100),
            "2030-03": HistoricalHouseholdMonth("2030-03", 10_000, 100),
        })
        signal = amount_left_trend(SELECTED_MONTHS, rows, rows)
        self.assertNotEqual(signal.kind if signal else None, "repeated_overspending")

    def test_spending_growth_and_growth_gap_thresholds_are_inclusive(self) -> None:
        rows = self.history()
        rows.update({
            month: HistoricalHouseholdMonth(month, 10_000, 5_500)
            for month in SELECTED_MONTHS
        })
        signal = amount_left_trend(SELECTED_MONTHS, rows, rows)
        self.assertEqual(signal.kind, "spending_outgrew_income")
        self.assertEqual(signal.severity, 2)
        self.assertAlmostEqual(signal.spending_growth, 0.10)
        self.assertAlmostEqual(signal.income_growth, 0)
        self.assertAlmostEqual(signal.growth_gap, 0.10)

    def test_subthreshold_growth_does_not_qualify(self) -> None:
        rows = self.history()
        rows.update({
            month: HistoricalHouseholdMonth(month, 10_000, 5_499)
            for month in SELECTED_MONTHS
        })
        self.assertIsNone(amount_left_trend(SELECTED_MONTHS, rows, rows))

    def test_amount_left_requires_shekels_and_percentage_in_same_direction(self) -> None:
        rows = self.history()
        rows.update({
            month: HistoricalHouseholdMonth(month, 8_750, 5_250)
            for month in SELECTED_MONTHS
        })
        signal = amount_left_trend(SELECTED_MONTHS, rows, rows)
        self.assertEqual(signal.kind, "amount_left_shift")
        self.assertEqual(signal.amount_change, -1_500)
        self.assertAlmostEqual(signal.percentage_point_change, -10)

        mixed = self.history()
        mixed.update({
            month: HistoricalHouseholdMonth(month, 5_833.333333, 2_333.333333)
            for month in SELECTED_MONTHS
        })
        self.assertIsNone(amount_left_trend(SELECTED_MONTHS, mixed, mixed))

    def test_higher_severity_later_window_wins(self) -> None:
        selected = (
            "2030-01", "2030-02", "2030-03", "2030-04", "2030-05", "2030-06",
        )
        rows = self.history()
        rows.update({
            month: HistoricalHouseholdMonth(month, 8_750, 5_250)
            for month in selected[:3]
        })
        rows.update({
            "2030-04": HistoricalHouseholdMonth("2030-04", 10_000, 11_000),
            "2030-05": HistoricalHouseholdMonth("2030-05", 10_000, 12_000),
            "2030-06": HistoricalHouseholdMonth("2030-06", 10_000, 9_000),
        })
        signal = amount_left_trend(selected, rows, rows)
        self.assertEqual(signal.kind, "repeated_overspending")
        self.assertEqual(signal.start_month, "2030-03")

    def test_lifecycle_reports_still_visible_from_latest_two_months(self) -> None:
        selected = (*SELECTED_MONTHS, "2030-04")
        rows = self.history()
        rows.update({
            month: HistoricalHouseholdMonth(month, 10_000, 5_500)
            for month in selected
        })
        signal = amount_left_trend(selected, rows, rows)
        self.assertEqual(signal.duration, 4)
        self.assertTrue(signal.active)


class CategoryRoutineShiftRuleTests(unittest.TestCase):
    def category_history(
        self,
        post_values: tuple[float, ...],
        *,
        baseline: float = 1_000,
    ) -> dict[str, dict[str, float]]:
        return {
            **{month: {"Synthetic category": baseline} for month in PRE_MONTHS},
            **{
                month: {"Synthetic category": value} if value else {}
                for month, value in zip(SELECTED_MONTHS, post_values)
            },
        }

    def test_category_totals_exclude_events_refunds_and_uncovered_months(self) -> None:
        result = routine_category_totals(
            ("2030-01", "2030-02"),
            [
                HistoricalCategoryTransaction("2030-01", "Food", "One", 100),
                HistoricalCategoryTransaction("2030-01", None, "Two", 50),
                HistoricalCategoryTransaction("2030-01", "Food", "Three", -25),
                HistoricalCategoryTransaction("2030-01", "Food", "Four", 500, 7),
                HistoricalCategoryTransaction("2030-03", "Food", "Five", 900),
            ],
        )
        self.assertEqual(result, {
            "2030-01": {"Food": 100, "Needs review": 50},
            "2030-02": {},
        })

    def test_requires_three_active_baseline_months(self) -> None:
        history = self.category_history((1_500, 1_500, 1_001))
        for month in PRE_MONTHS[:4]:
            history[month] = {}
        self.assertEqual(category_routine_shifts(SELECTED_MONTHS, history), ())

    def test_increase_thresholds_are_inclusive(self) -> None:
        findings = category_routine_shifts(
            SELECTED_MONTHS,
            self.category_history((1_500, 1_500, 1_001)),
        )
        self.assertEqual(len(findings), 1)
        signal = findings[0]
        self.assertEqual(signal.observation_type, CATEGORY_ROUTINE_SHIFTED)
        self.assertTrue(signal.higher)
        self.assertEqual(signal.baseline, 1_000)
        self.assertEqual(signal.post_values, (1_500, 1_500, 1_001))

    def test_increase_requires_two_post_months_with_spending(self) -> None:
        self.assertEqual(category_routine_shifts(
            SELECTED_MONTHS,
            self.category_history((2_000, 0, 0)),
        ), ())

    def test_decrease_can_reach_zero_in_covered_months(self) -> None:
        findings = category_routine_shifts(
            SELECTED_MONTHS,
            self.category_history((500, 500, 0), baseline=1_500),
        )
        self.assertEqual(len(findings), 1)
        self.assertFalse(findings[0].higher)
        self.assertEqual(findings[0].post_values, (500, 500, 0))

    def test_isolated_change_or_baseline_return_does_not_qualify(self) -> None:
        isolated = self.category_history((1_500, 1_001, 1_001))
        returned = self.category_history((1_500, 1_500, 1_000))
        self.assertEqual(category_routine_shifts(SELECTED_MONTHS, isolated), ())
        self.assertEqual(category_routine_shifts(SELECTED_MONTHS, returned), ())

    def test_longest_candidate_wins_and_partial_month_is_ignored(self) -> None:
        selected = (*SELECTED_MONTHS, "2030-04")
        history = self.category_history((1_500, 1_500, 1_100))
        history["2030-04"] = {"Synthetic category": 100}
        with_partial = category_routine_shifts(
            selected, history, partial_month="2030-04",
        )[0]
        without_partial = category_routine_shifts(selected, history)[0]
        self.assertEqual(with_partial.duration, 3)
        self.assertTrue(with_partial.active)
        self.assertFalse(without_partial.active)

    def test_drivers_use_positive_non_event_transactions_and_keep_top_three(self) -> None:
        history = self.category_history((1_500, 1_500, 1_001))
        rows = [
            HistoricalCategoryTransaction("2029-12", "Synthetic category", "Third", 300),
            HistoricalCategoryTransaction("2030-01", "Synthetic category", "First", 700),
            HistoricalCategoryTransaction("2030-02", "Synthetic category", "Second", 500),
            HistoricalCategoryTransaction("2030-03", "Synthetic category", "Fourth", 100),
            HistoricalCategoryTransaction("2030-01", "Synthetic category", "Event", 5_000, 4),
            HistoricalCategoryTransaction("2030-01", "Synthetic category", "Refund", -50),
            HistoricalCategoryTransaction("2030-01", "Other", "Wrong category", 9_000),
        ]
        signal = category_routine_shifts(SELECTED_MONTHS, history, rows)[0]
        self.assertEqual(signal.drivers, ("First", "Second", "Third"))


class RecurringBurdenShiftRuleTests(unittest.TestCase):
    def series(
        self,
        series_id: str,
        amount: float,
        *,
        cadence: str = "Monthly",
        status: str = "active",
        label: str = "",
    ) -> HistoricalRecurringSeries:
        return HistoricalRecurringSeries(
            series_id, amount, cadence, status, label or series_id,
        )

    def history(
        self,
        pre_amount: float = 1_000,
        post_amount: float = 1_000,
    ) -> dict[str, HistoricalRecurringMonth]:
        return {
            **{
                month: HistoricalRecurringMonth(
                    month, (self.series("base", pre_amount),), 1,
                )
                for month in PRE_MONTHS
            },
            **{
                month: HistoricalRecurringMonth(
                    month, (self.series("base", post_amount),), 1,
                )
                for month in SELECTED_MONTHS
            },
        }

    def test_non_monthly_cadences_are_converted_to_monthly_equivalents(self) -> None:
        yearly = self.series("yearly", 1_200, cadence="Yearly")
        weekly = self.series("weekly", 25, cadence="Weekly")
        history = {
            month: HistoricalRecurringMonth(month, (yearly, weekly), 2)
            for month in (*PRE_MONTHS, *SELECTED_MONTHS)
        }
        changed = self.series("yearly", 2_400, cadence="Yearly")
        for month in SELECTED_MONTHS:
            history[month] = HistoricalRecurringMonth(month, (changed, weekly), 2)
        signal = recurring_burden_shift(SELECTED_MONTHS, history, history)
        self.assertEqual(signal.cost_baseline, 200)
        self.assertEqual(signal.cost_after, 300)
        self.assertTrue(signal.cost_shift)

    def test_cost_thresholds_are_inclusive(self) -> None:
        signal = recurring_burden_shift(
            SELECTED_MONTHS, self.history(), self.history(post_amount=1_150),
        )
        self.assertEqual(signal.observation_type, RECURRING_BURDEN_SHIFTED)
        self.assertTrue(signal.cost_shift)
        self.assertFalse(signal.count_shift)
        self.assertEqual(signal.cost_after, 1_150)

    def test_count_shift_requires_two_supporting_post_months(self) -> None:
        history = self.history()
        history.update({
            "2030-01": HistoricalRecurringMonth(
                "2030-01", (self.series("base", 1_000),), 4,
            ),
            "2030-02": HistoricalRecurringMonth(
                "2030-02", (self.series("base", 1_000),), 4,
            ),
            "2030-03": HistoricalRecurringMonth(
                "2030-03", (self.series("base", 1_000),), 2,
            ),
        })
        signal = recurring_burden_shift(SELECTED_MONTHS, history, history)
        self.assertTrue(signal.count_shift)
        self.assertFalse(signal.cost_shift)
        self.assertEqual(signal.count_baseline, 1)
        self.assertEqual(signal.count_after, 10 / 3)

        history["2030-02"] = HistoricalRecurringMonth(
            "2030-02", (self.series("base", 1_000),), 1,
        )
        self.assertIsNone(recurring_burden_shift(SELECTED_MONTHS, history, history))

    def test_cost_and_count_can_shift_on_the_same_finding(self) -> None:
        history = self.history()
        for month in SELECTED_MONTHS:
            history[month] = HistoricalRecurringMonth(
                month,
                (
                    self.series("base", 1_000),
                    self.series("new-a", 100),
                    self.series("new-b", 100),
                ),
                3,
            )
        signal = recurring_burden_shift(SELECTED_MONTHS, history, history)
        self.assertTrue(signal.cost_shift)
        self.assertTrue(signal.count_shift)

    def test_inactive_series_do_not_add_cost_but_metric_count_takes_precedence(self) -> None:
        history = self.history()
        for month in SELECTED_MONTHS:
            history[month] = HistoricalRecurringMonth(
                month,
                (
                    self.series("base", 1_000),
                    self.series("ended", 9_000, status="ended"),
                ),
                4,
            )
        signal = recurring_burden_shift(SELECTED_MONTHS, history, history)
        self.assertTrue(signal.count_shift)
        self.assertFalse(signal.cost_shift)
        self.assertEqual(signal.cost_after, 1_000)

    def test_started_ended_and_changed_evidence_uses_series_identity(self) -> None:
        history = {}
        before = (
            self.series("kept", 500, label="Kept service"),
            self.series("ended", 500, label="Ended service"),
        )
        after = (
            self.series("kept", 700, label="Kept service"),
            self.series("started", 500, label="Started service"),
        )
        for month in PRE_MONTHS:
            history[month] = HistoricalRecurringMonth(month, before, 2)
        for month in SELECTED_MONTHS:
            history[month] = HistoricalRecurringMonth(month, after, 2)
        signal = recurring_burden_shift(SELECTED_MONTHS, history, history)
        self.assertEqual(signal.started, ("Started service",))
        self.assertEqual(signal.ended, ("Ended service",))
        self.assertEqual(len(signal.changed), 1)
        self.assertEqual(signal.changed[0].name, "Kept service")
        self.assertEqual(signal.changed[0].before, 500)
        self.assertEqual(signal.changed[0].after, 700)

    def test_subthreshold_cost_and_count_changes_are_suppressed(self) -> None:
        history = self.history()
        for month in SELECTED_MONTHS:
            history[month] = HistoricalRecurringMonth(
                month,
                (self.series("base", 1_099), self.series("extra", 0)),
                2,
            )
        self.assertIsNone(recurring_burden_shift(SELECTED_MONTHS, history, history))

    def test_partial_month_is_removed_from_lifecycle(self) -> None:
        selected = (*SELECTED_MONTHS, "2030-04")
        history = self.history(post_amount=1_200)
        history["2030-04"] = HistoricalRecurringMonth(
            "2030-04", (self.series("base", 100),), 1,
        )
        with_partial = recurring_burden_shift(
            selected, history, history, partial_month="2030-04",
        )
        without_partial = recurring_burden_shift(selected, history, history)
        self.assertTrue(with_partial.active)
        self.assertFalse(without_partial.active)


class PersistentInstallmentBurdenRuleTests(unittest.TestCase):
    MONTHS = (
        "2030-01", "2030-02", "2030-03", "2030-04",
        "2030-05", "2030-06", "2030-07",
    )

    def history(
        self,
        amounts: tuple[float, ...],
        plan_sets: tuple[tuple[HistoricalInstallmentPlan, ...], ...] | None = None,
    ) -> dict[str, HistoricalInstallmentMonth]:
        plans = plan_sets or tuple(
            (HistoricalInstallmentPlan(plan_id="plan-a"),) for _ in amounts
        )
        return {
            month: HistoricalInstallmentMonth(month, amount, month_plans)
            for month, amount, month_plans in zip(self.MONTHS, amounts, plans)
        }

    def test_six_month_thresholds_are_inclusive(self) -> None:
        history = self.history((1_000,) * 6)
        signal = persistent_installment_burden(self.MONTHS[:6], history)
        self.assertEqual(signal.observation_type, PERSISTENT_INSTALLMENT_BURDEN)
        self.assertEqual(signal.average_burden, 1_000)
        self.assertEqual(signal.duration, 6)
        self.assertTrue(signal.active)

    def test_every_month_must_clear_the_minimum(self) -> None:
        history = self.history((499, 1_101, 1_100, 1_100, 1_100, 1_100))
        self.assertIsNone(persistent_installment_burden(self.MONTHS[:6], history))

    def test_average_must_clear_the_minimum(self) -> None:
        history = self.history((900,) * 6)
        self.assertIsNone(persistent_installment_burden(self.MONTHS[:6], history))

    def test_one_long_plan_is_persistent_without_replacement(self) -> None:
        history = self.history((1_000,) * 6)
        signal = persistent_installment_burden(self.MONTHS[:6], history)
        self.assertFalse(signal.replacements)
        self.assertEqual(signal.starts, 0)
        self.assertEqual(signal.endings, 0)

    def test_two_plan_starts_and_endings_explain_replacement(self) -> None:
        plan = lambda value: HistoricalInstallmentPlan(plan_id=value)
        plan_sets = (
            (plan("a"), plan("b")),
            (plan("a"), plan("c")),
            (plan("c"), plan("d")),
            (plan("c"), plan("d")),
            (plan("c"), plan("d")),
            (plan("c"), plan("d")),
        )
        history = self.history((1_000,) * 6, plan_sets)
        signal = persistent_installment_burden(self.MONTHS[:6], history)
        self.assertEqual(signal.starts, 2)
        self.assertEqual(signal.endings, 2)
        self.assertTrue(signal.replacements)

    def test_plan_fallback_identity_distinguishes_separate_purchases(self) -> None:
        first = HistoricalInstallmentPlan(
            source_alias="Synthetic merchant",
            original_purchase_date="2030-01-01",
            original_amount=1_200,
            installment_total=6,
        )
        second = HistoricalInstallmentPlan(
            source_alias="Synthetic merchant",
            original_purchase_date="2030-02-01",
            original_amount=1_200,
            installment_total=6,
        )
        self.assertNotEqual(first.identity, second.identity)

    def test_duration_extends_until_burden_falls_below_500(self) -> None:
        history = self.history((1_000,) * 7)
        signal = persistent_installment_burden(self.MONTHS, history)
        self.assertEqual(signal.start_month, "2030-01")
        self.assertEqual(signal.duration, 7)
        self.assertTrue(signal.active)

        history[self.MONTHS[-1]] = HistoricalInstallmentMonth(
            self.MONTHS[-1], 499,
        )
        signal = persistent_installment_burden(self.MONTHS, history)
        self.assertEqual(signal.duration, 6)
        self.assertFalse(signal.active)

    def test_partial_month_is_removed_before_qualification(self) -> None:
        history = self.history((1_000,) * 6 + (100,))
        with_partial = persistent_installment_burden(
            self.MONTHS, history, partial_month="2030-07",
        )
        without_partial = persistent_installment_burden(self.MONTHS, history)
        self.assertTrue(with_partial.active)
        self.assertFalse(without_partial.active)


if __name__ == "__main__":
    unittest.main()
