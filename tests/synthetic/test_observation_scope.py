from __future__ import annotations

import unittest

from clearspend.observations.scope import build_observation_scope


AVAILABLE = (
    "2029-11", "2029-12", "2030-01", "2030-02", "2030-03", "2030-04",
)


class ObservationScopeTests(unittest.TestCase):
    def test_month_scope_analyzes_only_selected_month_but_keeps_prior_history(self) -> None:
        scope = build_observation_scope(
            period="month",
            available_months=AVAILABLE,
            selected_month="2030-03",
            period_start="2030-03-01",
            period_end="2030-03-31",
        )
        self.assertEqual(scope.target_months, ("2030-03",))
        self.assertEqual(scope.history_months, AVAILABLE[:-1])
        self.assertEqual(scope.recurring_months, ("2030-03",))
        self.assertFalse(scope.historical)

    def test_historical_scope_uses_period_range_and_fetches_all_earlier_history(self) -> None:
        scope = build_observation_scope(
            period="latest",
            available_months=AVAILABLE,
            period_start="2030-01-01",
            period_end="2030-03-31",
        )
        self.assertEqual(scope.target_months, ("2030-01", "2030-02", "2030-03"))
        self.assertEqual(scope.history_months, AVAILABLE[:-1])
        self.assertEqual(scope.recurring_months, AVAILABLE[:-1])
        self.assertTrue(scope.historical)

    def test_all_time_target_still_respects_backend_period_bounds(self) -> None:
        scope = build_observation_scope(
            period="all",
            available_months=AVAILABLE,
            period_start="2029-12-01",
            period_end="2030-04-30",
        )
        self.assertEqual(scope.target_months, AVAILABLE[1:])
        self.assertEqual(scope.observed_start, "2029-12")
        self.assertEqual(scope.observed_end, "2030-04")

    def test_selected_month_falls_back_to_period_start(self) -> None:
        scope = build_observation_scope(
            period="month",
            available_months=AVAILABLE,
            period_start="2030-02-01",
            period_end="2030-02-28",
        )
        self.assertEqual(scope.selected_month, "2030-02")
        self.assertEqual(scope.target_months, ("2030-02",))

    def test_month_target_preserves_selected_month_even_without_imported_rows(self) -> None:
        scope = build_observation_scope(
            period="month",
            available_months=AVAILABLE,
            selected_month="2030-05",
            period_start="2030-05-01",
            period_end="2030-05-31",
        )
        self.assertEqual(scope.target_months, ("2030-05",))
        self.assertEqual(scope.history_months, AVAILABLE)
        self.assertEqual(scope.recurring_months, ("2030-05",))

    def test_months_are_deduplicated_and_sorted(self) -> None:
        scope = build_observation_scope(
            period="all",
            available_months=("2030-02", "2030-01", "2030-02"),
            period_start="2030-01-01",
            period_end="2030-02-28",
        )
        self.assertEqual(scope.target_months, ("2030-01", "2030-02"))
        self.assertEqual(scope.history_months, ("2030-01", "2030-02"))


if __name__ == "__main__":
    unittest.main()
