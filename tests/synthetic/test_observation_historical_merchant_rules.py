from __future__ import annotations

import unittest

from clearspend.observations.historical_merchant_rules import (
    MERCHANT_HABIT_SHIFTED,
    HistoricalMerchantTransaction,
    established_merchant_habit_shifts,
    newly_regular_merchant_habits,
)


PRE_MONTHS = ("2029-07", "2029-08", "2029-09", "2029-10", "2029-11", "2029-12")
SELECTED_MONTHS = ("2030-01", "2030-02", "2030-03", "2030-04", "2030-05", "2030-06")
ALL_MONTHS = (*PRE_MONTHS, *SELECTED_MONTHS)


def transaction(
    identity: str,
    date: str,
    amount: float,
    *,
    merchant_raw: str | None = None,
    category: str = "Synthetic category",
    installment_total: int | None = None,
    event_id: int | None = None,
) -> HistoricalMerchantTransaction:
    return HistoricalMerchantTransaction(
        identity=identity,
        merchant_label=f"{identity} label",
        merchant_raw=merchant_raw or identity,
        transaction_date=date,
        personal_amount=amount,
        category=category,
        installment_total=installment_total,
        event_id=event_id,
    )


class NewlyRegularMerchantHabitTests(unittest.TestCase):
    def test_three_consecutive_months_can_qualify_by_spending(self) -> None:
        rows = [
            transaction("merchant-a", f"2030-0{month}-10", 250)
            for month in range(1, 4)
        ]
        findings = newly_regular_merchant_habits(
            SELECTED_MONTHS, ALL_MONTHS, rows,
        )
        self.assertEqual(len(findings), 1)
        signal = findings[0]
        self.assertEqual(signal.observation_type, MERCHANT_HABIT_SHIFTED)
        self.assertEqual(signal.start_month, "2030-01")
        self.assertEqual(signal.establishment_months, SELECTED_MONTHS[:3])
        self.assertTrue(signal.spending_qualified)
        self.assertFalse(signal.frequency_qualified)
        self.assertEqual(signal.average_monthly_spending, 250)

    def test_three_consecutive_months_can_qualify_by_frequency(self) -> None:
        rows = [
            transaction("merchant-a", f"2030-0{month}-{day:02d}", 10)
            for month in range(1, 4)
            for day in (5, 15)
        ]
        signal = newly_regular_merchant_habits(
            SELECTED_MONTHS, ALL_MONTHS, rows,
        )[0]
        self.assertFalse(signal.spending_qualified)
        self.assertTrue(signal.frequency_qualified)
        self.assertEqual(signal.purchase_count, 6)
        self.assertEqual(signal.purchase_days, 6)

    def test_four_of_six_uses_the_stricter_frequency_requirement(self) -> None:
        rows = [
            transaction("merchant-a", f"2030-0{month}-{day:02d}", 10)
            for month in (1, 2, 4, 6)
            for day in (5, 15)
        ]
        signal = newly_regular_merchant_habits(
            SELECTED_MONTHS, ALL_MONTHS, rows,
        )[0]
        self.assertEqual(signal.establishment_months, SELECTED_MONTHS)
        self.assertEqual(signal.purchase_count, 8)
        self.assertEqual(signal.purchase_days, 8)
        self.assertTrue(signal.frequency_qualified)

    def test_more_than_one_active_baseline_month_prevents_new_habit_claim(self) -> None:
        rows = [
            transaction("merchant-a", "2029-08-10", 250),
            transaction("merchant-a", "2029-11-10", 250),
            *[
                transaction("merchant-a", f"2030-0{month}-10", 250)
                for month in range(1, 4)
            ],
        ]
        self.assertEqual(newly_regular_merchant_habits(
            SELECTED_MONTHS, ALL_MONTHS, rows,
        ), ())

    def test_recurring_events_installments_transfers_and_refunds_are_excluded(self) -> None:
        rows = []
        for month in range(1, 4):
            date = f"2030-0{month}-10"
            rows.extend((
                transaction("recurring", date, 250, merchant_raw="reviewed-alias"),
                transaction("event", date, 250, event_id=7),
                transaction("installment", date, 250, installment_total=6),
                transaction("transfer", date, 250, category="העברת כספים"),
                transaction("refund", date, -250),
            ))
        self.assertEqual(newly_regular_merchant_habits(
            SELECTED_MONTHS,
            ALL_MONTHS,
            rows,
            recurring_aliases=("reviewed-alias",),
        ), ())

    def test_purchase_date_controls_month_membership(self) -> None:
        rows = [
            transaction("merchant-a", "2030-01-31", 250),
            transaction("merchant-a", "2030-02-01", 250),
            transaction("merchant-a", "2030-03-01", 250),
        ]
        signal = newly_regular_merchant_habits(
            SELECTED_MONTHS, ALL_MONTHS, rows,
        )[0]
        self.assertEqual(signal.monthly_spending, (250, 250, 250))

    def test_later_activity_and_buying_more_are_reported_separately(self) -> None:
        rows = [
            transaction("merchant-a", f"2030-0{month}-10", 250)
            for month in range(1, 4)
        ]
        rows.extend(
            transaction("merchant-a", f"2030-0{month}-{day:02d}", 50)
            for month in range(4, 7)
            for day in (2, 8, 14, 20)
        )
        signal = newly_regular_merchant_habits(
            SELECTED_MONTHS, ALL_MONTHS, rows,
        )[0]
        self.assertEqual(signal.later_months, 3)
        self.assertEqual(signal.later_active_months, 3)
        self.assertEqual(signal.established_frequency, 1)
        self.assertEqual(signal.recent_frequency, 4)
        self.assertTrue(signal.buying_more)
        self.assertTrue(signal.still_visible)

    def test_partial_month_is_removed_before_recent_activity_is_measured(self) -> None:
        rows = [
            transaction("merchant-a", f"2030-0{month}-10", 250)
            for month in range(1, 6)
        ]
        without_partial = newly_regular_merchant_habits(
            SELECTED_MONTHS, ALL_MONTHS, rows,
        )[0]
        with_partial = newly_regular_merchant_habits(
            SELECTED_MONTHS,
            ALL_MONTHS,
            rows,
            partial_month="2030-06",
        )[0]
        self.assertTrue(without_partial.still_visible)
        self.assertTrue(with_partial.still_visible)
        self.assertEqual(with_partial.later_months, 2)


class EstablishedMerchantHabitShiftTests(unittest.TestCase):
    def rows(
        self,
        pre_count: int,
        post_counts: tuple[int, int, int],
        *,
        pre_amount: float = 100,
        post_amount: float = 100,
    ) -> list[HistoricalMerchantTransaction]:
        rows = [
            transaction(
                "merchant-a", f"{month}-{day + 1:02d}", pre_amount,
            )
            for month in PRE_MONTHS
            for day in range(pre_count)
        ]
        rows.extend(
            transaction(
                "merchant-a", f"{month}-{day + 1:02d}", post_amount,
            )
            for month, count in zip(SELECTED_MONTHS[:3], post_counts)
            for day in range(count)
        )
        return rows

    def shift(self, rows: list[HistoricalMerchantTransaction]):
        findings = established_merchant_habit_shifts(
            SELECTED_MONTHS[:3], ALL_MONTHS, rows,
        )
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].observation_type, MERCHANT_HABIT_SHIFTED)
        return findings[0]

    def test_buying_more_often_requires_stable_typical_amount(self) -> None:
        signal = self.shift(self.rows(2, (4, 4, 4)))
        self.assertEqual(signal.kind, "Buying more often")
        self.assertEqual(signal.pre_count, 2)
        self.assertEqual(signal.post_count, 4)
        self.assertEqual(signal.post_counts, (4, 4, 4))

        changed_price = self.rows(2, (4, 4, 4), post_amount=130)
        self.assertEqual(established_merchant_habit_shifts(
            SELECTED_MONTHS[:3], ALL_MONTHS, changed_price,
        ), ())

    def test_buying_less_often_allows_one_zero_purchase_month(self) -> None:
        signal = self.shift(self.rows(4, (1, 1, 0)))
        self.assertEqual(signal.kind, "Buying less often")
        self.assertEqual(signal.post_count, 2 / 3)
        self.assertTrue(signal.active)

    def test_typical_purchase_amount_increase_thresholds_are_inclusive(self) -> None:
        signal = self.shift(self.rows(2, (2, 2, 2), post_amount=120))
        self.assertEqual(signal.kind, "Typical purchase amount increased")
        self.assertEqual(signal.pre_typical_amount, 100)
        self.assertEqual(signal.post_typical_amount, 120)

    def test_typical_purchase_amount_decrease_thresholds_are_inclusive(self) -> None:
        signal = self.shift(self.rows(2, (2, 2, 2), post_amount=80))
        self.assertEqual(signal.kind, "Typical purchase amount decreased")
        self.assertEqual(signal.post_typical_amount, 80)

    def test_requires_three_active_baseline_and_two_active_post_months(self) -> None:
        too_little_baseline = self.rows(2, (4, 4, 4))
        too_little_baseline = [
            row for row in too_little_baseline
            if row.purchase_month not in PRE_MONTHS[:4]
        ]
        self.assertEqual(established_merchant_habit_shifts(
            SELECTED_MONTHS[:3], ALL_MONTHS, too_little_baseline,
        ), ())

        one_post_month = self.rows(4, (1, 0, 0))
        self.assertEqual(established_merchant_habit_shifts(
            SELECTED_MONTHS[:3], ALL_MONTHS, one_post_month,
        ), ())

    def test_merchants_that_became_regular_are_not_reported_twice(self) -> None:
        rows = [
            transaction("merchant-a", f"2030-0{month}-10", 250)
            for month in range(1, 4)
        ]
        self.assertEqual(established_merchant_habit_shifts(
            SELECTED_MONTHS[:3], ALL_MONTHS, rows,
        ), ())

    def test_lifecycle_stops_when_frequency_returns_to_baseline(self) -> None:
        rows = self.rows(2, (4, 4, 4))
        rows.extend(
            transaction("merchant-a", f"2030-04-{day + 1:02d}", 100)
            for day in range(2)
        )
        signal = established_merchant_habit_shifts(
            SELECTED_MONTHS[:4], ALL_MONTHS, rows,
        )[0]
        self.assertEqual(signal.duration, 3)
        self.assertFalse(signal.active)


if __name__ == "__main__":
    unittest.main()
