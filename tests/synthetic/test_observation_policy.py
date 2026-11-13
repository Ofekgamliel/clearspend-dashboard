from __future__ import annotations

import unittest

from clearspend.observations.policy import (
    OBSERVATION_RESOLUTIONS,
    observation_review_policy,
)


class ObservationReviewPolicyTests(unittest.TestCase):
    def test_only_three_observation_types_are_reviewable(self) -> None:
        self.assertEqual(OBSERVATION_RESOLUTIONS, {
            "POSSIBLE DUPLICATE": "not_duplicate",
            "ADDITIONAL RECURRING CHARGE": "expected_charge",
            "UNUSUAL TRANSACTION": "not_unusual",
        })
        self.assertIsNone(observation_review_policy("LARGE PURCHASE"))
        self.assertIsNone(observation_review_policy("MERCHANT HABIT SHIFTED"))

    def test_policy_lookup_normalizes_case_and_whitespace(self) -> None:
        policy = observation_review_policy("  possible duplicate  ")
        self.assertEqual(policy.observation_type, "POSSIBLE DUPLICATE")
        self.assertEqual(policy.resolution, "not_duplicate")

    def test_duplicate_policy_requires_at_least_two_transactions(self) -> None:
        policy = observation_review_policy("POSSIBLE DUPLICATE")
        self.assertFalse(policy.accepts_transaction_count(1))
        self.assertTrue(policy.accepts_transaction_count(2))
        self.assertTrue(policy.accepts_transaction_count(5))
        self.assertEqual(policy.activity_target, "transactions")

    def test_unusual_policy_requires_exactly_one_transaction(self) -> None:
        policy = observation_review_policy("UNUSUAL TRANSACTION")
        self.assertFalse(policy.accepts_transaction_count(0))
        self.assertTrue(policy.accepts_transaction_count(1))
        self.assertFalse(policy.accepts_transaction_count(2))
        self.assertEqual(policy.activity_target, "transaction")

    def test_recurring_policy_requires_series_context(self) -> None:
        policy = observation_review_policy("ADDITIONAL RECURRING CHARGE")
        self.assertTrue(policy.requires_recurring_series)
        self.assertEqual(policy.activity_target, "recurring_series")
        self.assertEqual(policy.action_label, "Expected charge")
        self.assertEqual(
            policy.resolved_label,
            "Marked as an expected separate charge",
        )


if __name__ == "__main__":
    unittest.main()
