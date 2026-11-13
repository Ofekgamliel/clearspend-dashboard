from __future__ import annotations

import unittest

from clearspend.observations.recurring_amount_rules import RecurringObservationCharge
from clearspend.observations.recurring_cycle_rules import (
    ADDITIONAL_RECURRING_CHARGE,
    additional_recurring_charges,
    recurring_review_key,
)


def charge(
    charge_id: int,
    transaction_date: str,
    *,
    amount: float = 100,
    merchant: str = "synthetic service",
    card: str = "0001",
) -> RecurringObservationCharge:
    return RecurringObservationCharge(
        id=charge_id,
        merchant_normalized=merchant,
        provider="synthetic",
        card_last4=card,
        transaction_date=transaction_date,
        personal_amount=amount,
    )


class RecurringCycleObservationRuleTests(unittest.TestCase):
    def test_requires_three_prior_charges_to_learn_the_cycle(self) -> None:
        rows = [
            charge(1, "2030-01-10"), charge(2, "2030-02-10"),
            charge(3, "2030-03-10"), charge(4, "2030-03-12"),
        ]
        self.assertEqual(additional_recurring_charges("series", "2030-03", rows), ())

    def test_one_charge_in_the_occurrence_window_is_not_additional(self) -> None:
        rows = [
            charge(1, "2029-12-10"), charge(2, "2030-01-10"),
            charge(3, "2030-02-10"), charge(4, "2030-03-10"),
        ]
        self.assertEqual(additional_recurring_charges("series", "2030-03", rows), ())

    def test_window_can_span_the_calendar_month_boundary(self) -> None:
        rows = [
            charge(1, "2029-11-30"), charge(2, "2029-12-31"),
            charge(3, "2030-01-31"), charge(4, "2030-02-25", amount=90),
            charge(5, "2030-03-02", amount=110),
        ]
        signal = additional_recurring_charges("series", "2030-02", rows)[0]
        self.assertEqual(signal.observation_type, ADDITIONAL_RECURRING_CHARGE)
        self.assertEqual(signal.expected_date, "2030-02-28")
        self.assertEqual(signal.transaction_ids, (4, 5))
        self.assertEqual(signal.occurrence_start, "2030-02-25")
        self.assertEqual(signal.occurrence_end, "2030-03-02")
        self.assertEqual(signal.total_amount, 200)

    def test_window_of_only_exact_duplicates_is_suppressed(self) -> None:
        rows = [
            charge(1, "2029-12-10"), charge(2, "2030-01-10"),
            charge(3, "2030-02-10"), charge(4, "2030-03-10"),
            charge(5, "2030-03-10"),
        ]
        self.assertEqual(additional_recurring_charges(
            "series", "2030-03", rows,
            duplicate_transaction_ids=(4, 5),
        ), ())

    def test_mixed_duplicate_and_separate_charges_keep_one_reviewable_window(self) -> None:
        rows = [
            charge(1, "2029-12-10"), charge(2, "2030-01-10"),
            charge(3, "2030-02-10"), charge(4, "2030-03-09"),
            charge(5, "2030-03-09"), charge(6, "2030-03-12"),
        ]
        signal = additional_recurring_charges(
            "series", "2030-03", rows,
            duplicate_transaction_ids=(4, 5),
        )[0]
        self.assertEqual(signal.transaction_ids, (4, 5, 6))
        self.assertEqual(signal.additional_count, 2)

    def test_exact_streams_are_evaluated_separately(self) -> None:
        rows = []
        for card, start in (("0001", 1), ("0002", 11)):
            rows.extend([
                charge(start, "2029-12-10", card=card),
                charge(start + 1, "2030-01-10", card=card),
                charge(start + 2, "2030-02-10", card=card),
                charge(start + 3, "2030-03-09", card=card),
                charge(start + 4, "2030-03-11", card=card),
            ])
        signals = additional_recurring_charges("series", "2030-03", rows)
        self.assertEqual(len(signals), 2)
        self.assertEqual(signals[0].transaction_ids, (4, 5))
        self.assertEqual(signals[1].transaction_ids, (14, 15))

    def test_only_latest_six_prior_days_and_stable_key_are_used(self) -> None:
        rows = [charge(1, "2029-08-01")]
        rows.extend(
            charge(index, f"{year_month}-20")
            for index, year_month in enumerate(
                ("2029-09", "2029-10", "2029-11", "2029-12", "2030-01", "2030-02"),
                start=2,
            )
        )
        rows.extend([charge(8, "2030-03-19"), charge(9, "2030-03-21")])
        signal = additional_recurring_charges("series/one", "2030-03", rows)[0]
        self.assertEqual(signal.learned_days, (20, 20, 20, 20, 20, 20))
        self.assertEqual(signal.expected_date, "2030-03-20")
        self.assertEqual(
            signal.finding_key,
            "ADDITIONAL RECURRING CHARGE:series%2Fone:2030-03-20:8,9",
        )
        self.assertEqual(
            recurring_review_key("series/one", "2030-03-20", [9, 8, 9]),
            signal.finding_key,
        )

    def test_half_day_median_uses_javascript_rounding_behavior(self) -> None:
        rows = [
            charge(1, "2029-11-10"), charge(2, "2029-12-11"),
            charge(3, "2030-01-10"), charge(4, "2030-02-11"),
            charge(5, "2030-03-10"), charge(6, "2030-03-12"),
        ]
        signal = additional_recurring_charges("series", "2030-03", rows)[0]
        self.assertEqual(signal.expected_date, "2030-03-11")


if __name__ == "__main__":
    unittest.main()
