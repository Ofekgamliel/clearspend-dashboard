from __future__ import annotations

import unittest

from clearspend.observations.transaction_rules import (
    ObservationTransaction,
    duplicate_review_key,
    possible_duplicate_groups,
    prior_identity_purchases,
    purchase_signal,
    stable_purchase_baseline,
    unusual_review_key,
)


def transaction(
    transaction_id: int,
    *,
    month: str = "2030-07",
    date: str = "2030-07-10",
    amount: float = 100,
    personal_amount: float | None = None,
    merchant: str = "synthetic merchant",
    category: str = "Synthetic category",
    card: str = "0001",
    installment_total: int | None = None,
) -> ObservationTransaction:
    return ObservationTransaction(
        id=transaction_id,
        merchant_normalized=merchant,
        canonical_merchant_id=merchant,
        category=category,
        provider="synthetic",
        card_last4=card,
        transaction_date=date,
        month=month,
        charged_amount=amount,
        charged_currency="ILS",
        personal_amount=amount if personal_amount is None else personal_amount,
        installment_total=installment_total,
    )


class ObservationTransactionRuleTests(unittest.TestCase):
    def test_duplicate_requires_every_exact_charge_field(self) -> None:
        rows = [
            transaction(2), transaction(1),
            transaction(3, card="0002"),
            transaction(4, date="2030-07-11"),
        ]
        candidates = possible_duplicate_groups(rows)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].transaction_ids, (1, 2))
        self.assertEqual(candidates[0].finding_key, "POSSIBLE DUPLICATE:1,2")

    def test_duplicate_excludes_installments_and_non_personal_charges(self) -> None:
        rows = [
            transaction(1, installment_total=3),
            transaction(2, installment_total=3),
            transaction(3, personal_amount=0),
            transaction(4, personal_amount=0),
        ]
        self.assertEqual(possible_duplicate_groups(rows), ())

    def test_stability_requires_five_purchases_three_months_and_seventy_five_percent(self) -> None:
        stable = [
            transaction(1, month="2030-01", amount=100),
            transaction(2, month="2030-01", amount=105),
            transaction(3, month="2030-02", amount=95),
            transaction(4, month="2030-03", amount=110),
            transaction(5, month="2030-03", amount=200),
        ]
        baseline = stable_purchase_baseline(stable)
        self.assertIsNotNone(baseline)
        self.assertEqual(baseline.median, 105)
        self.assertEqual(baseline.inside_band_count, 4)
        self.assertIsNone(stable_purchase_baseline(stable[:4]))
        self.assertIsNone(stable_purchase_baseline([
            transaction(index, month="2030-01", amount=100 + index) for index in range(1, 6)
        ]))

    def test_history_is_same_identity_and_previous_six_months_only(self) -> None:
        candidate = transaction(10)
        rows = [
            transaction(1, month="2030-01"),
            transaction(2, month="2029-12"),
            transaction(3, month="2030-06", merchant="other"),
            transaction(4, month="2030-07"),
            transaction(5, month="2030-06"),
        ]
        self.assertEqual([row.id for row in prior_identity_purchases(candidate, rows)], [1, 5])

    def test_large_purchase_requires_amount_and_monthly_share(self) -> None:
        candidate = transaction(10, amount=600)
        self.assertIsNone(purchase_signal(
            candidate, [], monthly_positive_personal_spending=10_000,
        ))
        signal = purchase_signal(candidate, [], monthly_positive_personal_spending=8_000)
        self.assertEqual(signal.observation_type, "LARGE PURCHASE")
        self.assertEqual(signal.monthly_share, 0.075)

    def test_unusual_purchase_requires_stable_history_multiplier_and_difference(self) -> None:
        history = [
            transaction(1, month="2030-01", amount=100),
            transaction(2, month="2030-02", amount=105),
            transaction(3, month="2030-03", amount=95),
            transaction(4, month="2030-04", amount=100),
            transaction(5, month="2030-05", amount=100),
        ]
        candidate = transaction(10, amount=260)
        signal = purchase_signal(candidate, history, monthly_positive_personal_spending=10_000)
        self.assertEqual(signal.observation_type, "UNUSUAL TRANSACTION")
        self.assertEqual(signal.baseline.purchase_count, 5)
        self.assertEqual(signal.finding_key, "UNUSUAL TRANSACTION:10")
        self.assertIsNone(purchase_signal(
            candidate, history, monthly_positive_personal_spending=10_000,
            merchant_activity_already_changed=True,
        ))

    def test_one_purchase_can_merge_large_and_unusual_signals(self) -> None:
        history = [
            transaction(index, month=f"2030-0{(index + 1) // 2}", amount=200)
            for index in range(1, 7)
        ]
        signal = purchase_signal(
            transaction(10, amount=600), history,
            monthly_positive_personal_spending=4_000,
        )
        self.assertEqual(signal.observation_type, "LARGE AND UNUSUAL PURCHASE")
        self.assertEqual(signal.ratio_to_median, 3)
        self.assertIsNone(signal.finding_key)

    def test_review_keys_are_deterministic(self) -> None:
        self.assertEqual(duplicate_review_key([8, 2, 8]), "POSSIBLE DUPLICATE:2,8")
        self.assertEqual(unusual_review_key(9), "UNUSUAL TRANSACTION:9")


if __name__ == "__main__":
    unittest.main()
