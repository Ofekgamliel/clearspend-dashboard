from __future__ import annotations

import unittest

from clearspend.observations.recurring_amount_rules import (
    FEE_AMOUNT_INCREASED,
    FIRST_FEE_OBSERVED,
    RECURRING_AMOUNT_INCREASED,
    RecurringObservationCharge,
    is_fee_description,
    recurring_charge_observation,
)


def charge(
    charge_id: int,
    amount: float,
    *,
    date: str | None = None,
    merchant: str = "synthetic service",
    card: str = "0001",
    original_amount: float | None = None,
    original_currency: str | None = None,
) -> RecurringObservationCharge:
    return RecurringObservationCharge(
        id=charge_id,
        merchant_normalized=merchant,
        provider="synthetic",
        card_last4=card,
        transaction_date=date or f"2030-{charge_id:02d}-10",
        personal_amount=amount,
        original_amount=original_amount,
        original_currency=original_currency,
    )


class RecurringAmountObservationRuleTests(unittest.TestCase):
    def test_fee_recognition_matches_supported_english_and_hebrew_terms(self) -> None:
        for value in ("monthly fee", "CARD COMMISSION", "דמי כרטיס", "עמלה", "ריבית"):
            with self.subTest(value=value):
                self.assertTrue(is_fee_description(value))
        self.assertFalse(is_fee_description("synthetic subscription"))

    def test_first_observed_fee_is_not_claimed_as_confirmed_new(self) -> None:
        signal = recurring_charge_observation(
            charge(7, 25, date="2030-07-10"), [],
            recurring_type="Scheduled obligation",
            series_description="דמי כרטיס",
        )
        self.assertEqual(signal.observation_type, FIRST_FEE_OBSERVED)
        self.assertFalse(signal.coverage_confirmed)
        self.assertEqual(signal.observed_amount, 25)

    def test_no_history_does_not_create_a_non_fee_amount_finding(self) -> None:
        self.assertIsNone(recurring_charge_observation(
            charge(7, 25, date="2030-07-10"), [],
            recurring_type="Fixed recurring",
            series_description="synthetic subscription",
        ))

    def test_exact_alias_provider_and_card_define_the_comparison_stream(self) -> None:
        current = charge(7, 110, date="2030-07-10")
        unrelated = [
            charge(1, 10, date="2030-01-10", merchant="other"),
            charge(2, 10, date="2030-02-10", card="0002"),
            charge(3, 10, date="2030-08-10"),
        ]
        self.assertIsNone(recurring_charge_observation(
            current, unrelated,
            recurring_type="Fixed recurring",
            series_description="synthetic subscription",
        ))

    def test_fixed_charge_uses_only_the_latest_three_matching_charges(self) -> None:
        history = [charge(index, amount) for index, amount in enumerate(
            (10, 20, 100, 110, 120, 130), start=1,
        )]
        signal = recurring_charge_observation(
            charge(7, 121), history,
            recurring_type="Fixed recurring",
            series_description="synthetic subscription",
        )
        self.assertEqual(signal.observation_type, RECURRING_AMOUNT_INCREASED)
        self.assertEqual(signal.baseline, 120)
        self.assertEqual(signal.increase_above_comparison, 1)
        self.assertEqual(signal.comparison_charge_ids, (4, 5, 6))

    def test_fixed_charge_increase_below_one_shekel_is_suppressed(self) -> None:
        self.assertIsNone(recurring_charge_observation(
            charge(4, 100.99), [charge(1, 100), charge(2, 100), charge(3, 100)],
            recurring_type="Fixed recurring",
            series_description="synthetic subscription",
        ))

    def test_variable_charge_must_exceed_the_observed_maximum(self) -> None:
        history = [charge(1, 80), charge(2, 120), charge(3, 100)]
        self.assertIsNone(recurring_charge_observation(
            charge(4, 120.99), history,
            recurring_type="Usage-based recurring",
            series_description="synthetic utility",
        ))
        signal = recurring_charge_observation(
            charge(4, 121), history,
            recurring_type="Usage-based recurring",
            series_description="synthetic utility",
        )
        self.assertEqual(signal.observed_maximum, 120)
        self.assertEqual(signal.increase_above_comparison, 1)
        self.assertFalse(signal.fixed)

    def test_foreign_subscription_uses_same_original_currency_not_ils(self) -> None:
        history = [
            charge(1, 40, original_amount=10, original_currency="USD"),
            charge(2, 45, original_amount=10, original_currency="USD"),
            charge(3, 20, original_amount=5, original_currency="EUR"),
        ]
        self.assertIsNone(recurring_charge_observation(
            charge(4, 60, original_amount=10, original_currency="USD"), history,
            recurring_type="Fixed recurring",
            series_description="synthetic subscription",
        ))
        signal = recurring_charge_observation(
            charge(4, 30, original_amount=11, original_currency="USD"), history,
            recurring_type="Fixed recurring",
            series_description="synthetic subscription",
        )
        self.assertEqual(signal.comparison_currency, "USD")
        self.assertEqual(signal.baseline, 10)
        self.assertEqual(signal.comparison_charge_ids, (1, 2))

    def test_jpy_uses_a_one_hundred_unit_increase_threshold(self) -> None:
        history = [charge(1, 25, original_amount=1_000, original_currency="JPY")]
        self.assertIsNone(recurring_charge_observation(
            charge(2, 30, original_amount=1_099, original_currency="JPY"), history,
            recurring_type="Fixed recurring",
            series_description="synthetic subscription",
        ))
        signal = recurring_charge_observation(
            charge(2, 30, original_amount=1_100, original_currency="JPY"), history,
            recurring_type="Fixed recurring",
            series_description="monthly fee",
        )
        self.assertEqual(signal.observation_type, FEE_AMOUNT_INCREASED)
        self.assertEqual(signal.threshold, 100)


if __name__ == "__main__":
    unittest.main()
