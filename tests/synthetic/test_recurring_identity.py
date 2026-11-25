from __future__ import annotations

import unittest
from decimal import Decimal

from clearspend.recurring.identity import (
    installment_occurrence_identity,
    installment_plan_identity,
    recurring_occurrence_identity,
    recurring_series_identity,
    unexpected_actual_identity,
)


class RecurringIdentityTests(unittest.TestCase):
    def test_installment_identity_is_deterministic_and_amount_format_independent(self) -> None:
        first = installment_plan_identity(
            "synthetic", "1234", "synthetic device", "2030-01-05", "400.00", 4,
        )
        second = installment_plan_identity(
            "synthetic", "1234", "synthetic device", "2030-01-05", Decimal("400"), 4,
        )

        self.assertEqual(first, second)
        self.assertTrue(first.startswith("commitment_"))

    def test_installment_identity_keeps_parallel_cards_distinct(self) -> None:
        first = installment_plan_identity(
            "synthetic", "1234", "synthetic device", "2030-01-05", 400, 4,
        )
        second = installment_plan_identity(
            "synthetic", "5678", "synthetic device", "2030-01-05", 400, 4,
        )

        self.assertNotEqual(first, second)

    def test_public_occurrence_identifiers_are_deterministic_and_namespaced(self) -> None:
        series = recurring_series_identity("profile", "synthetic:0001")

        self.assertEqual(series, recurring_series_identity("profile", "synthetic:0001"))
        self.assertTrue(
            recurring_occurrence_identity(series, "2030-04")
            .startswith("occurrence_recurring_")
        )
        self.assertTrue(
            installment_occurrence_identity("commitment", 2)
            .startswith("occurrence_installment_")
        )
        actual = unexpected_actual_identity("private-transaction-key")
        self.assertTrue(actual.startswith("occurrence_actual_"))
        self.assertNotIn("private-transaction-key", actual)


if __name__ == "__main__":
    unittest.main()
