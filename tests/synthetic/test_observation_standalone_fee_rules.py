from __future__ import annotations

import unittest

from clearspend.observations.recurring_amount_rules import FIRST_FEE_OBSERVED
from clearspend.observations.standalone_fee_rules import (
    FeeObservationTransaction,
    first_observed_standalone_fees,
)


def transaction(
    transaction_id: int,
    month: str,
    *,
    amount: float = 25,
    canonical: str = "synthetic fee merchant",
    normalized: str = "synthetic fee alias",
    category: str = "Synthetic fees",
    description: str = "monthly fee",
) -> FeeObservationTransaction:
    return FeeObservationTransaction(
        id=transaction_id,
        canonical_merchant_id=canonical,
        merchant_normalized=normalized,
        category=category,
        month=month,
        transaction_date=f"{month}-10",
        personal_amount=amount,
        merchant_raw=description,
    )


class StandaloneFeeObservationRuleTests(unittest.TestCase):
    def test_positive_fee_without_history_is_first_observed_not_confirmed_new(self) -> None:
        signal = first_observed_standalone_fees(
            "2030-07", [transaction(1, "2030-07")],
        )[0]
        self.assertEqual(signal.observation_type, FIRST_FEE_OBSERVED)
        self.assertEqual(signal.observed_amount, 25)
        self.assertEqual(signal.history_start_month, "2029-07")
        self.assertEqual(signal.history_end_month, "2030-06")
        self.assertFalse(signal.coverage_confirmed)

    def test_non_fee_and_non_positive_current_rows_are_ignored(self) -> None:
        rows = [
            transaction(1, "2030-07", description="ordinary purchase"),
            transaction(2, "2030-07", amount=0),
            transaction(3, "2030-07", amount=-10),
        ]
        self.assertEqual(first_observed_standalone_fees("2030-07", rows), ())

    def test_reviewed_recurring_current_charge_is_excluded(self) -> None:
        rows = [transaction(1, "2030-07")]
        self.assertEqual(first_observed_standalone_fees(
            "2030-07", rows, recurring_transaction_ids=(1,),
        ), ())

    def test_prior_fee_suppresses_but_prior_non_fee_does_not(self) -> None:
        current = transaction(3, "2030-07")
        prior_fee = transaction(1, "2030-05")
        prior_purchase = transaction(2, "2030-06", description="ordinary purchase")
        self.assertEqual(first_observed_standalone_fees(
            "2030-07", [prior_fee, prior_purchase, current],
        ), ())
        signals = first_observed_standalone_fees(
            "2030-07", [prior_purchase, current],
        )
        self.assertEqual([signal.transaction_id for signal in signals], [3])

    def test_twelve_month_boundary_is_inclusive_and_older_history_is_not(self) -> None:
        current = transaction(3, "2030-07")
        self.assertEqual(first_observed_standalone_fees(
            "2030-07", [transaction(1, "2029-07"), current],
        ), ())
        signals = first_observed_standalone_fees(
            "2030-07", [transaction(2, "2029-06"), current],
        )
        self.assertEqual([signal.transaction_id for signal in signals], [3])

    def test_identity_uses_canonical_merchant_and_category(self) -> None:
        current = transaction(4, "2030-07", normalized="current alias")
        same_identity = transaction(1, "2030-06", normalized="older alias")
        other_category = transaction(2, "2030-06", category="Other category")
        same_month = transaction(3, "2030-07")
        self.assertEqual(first_observed_standalone_fees(
            "2030-07", [same_identity, other_category, same_month, current],
        ), ())
        signals = first_observed_standalone_fees(
            "2030-07", [other_category, same_month, current],
        )
        self.assertEqual(
            [signal.transaction_id for signal in signals],
            [3, 4],
        )


if __name__ == "__main__":
    unittest.main()
