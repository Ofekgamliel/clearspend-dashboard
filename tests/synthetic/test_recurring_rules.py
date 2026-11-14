from __future__ import annotations

import unittest

from clearspend.recurring.rules import assess_recurring_series, median, month_history


class RecurringRuleTests(unittest.TestCase):
    def test_fixed_monthly_series_detects_increase(self) -> None:
        assessment = assess_recurring_series(
            {"2030-01": 100, "2030-02": 100, "2030-03": 120},
            period="month",
            start_month="2030-03",
            end_month="2030-03",
            cadence_months=1,
            lifecycle_status="active",
            end_profile_month=None,
            recurring_type="Fixed recurring",
        )

        self.assertIsNotNone(assessment)
        self.assertEqual(assessment.status, "increased")
        self.assertEqual(assessment.amount, 120)
        self.assertEqual(assessment.typical_amount, 100)

    def test_missing_month_uses_existing_overdue_tolerance(self) -> None:
        expected = assess_recurring_series(
            {"2030-01": 100},
            period="month",
            start_month="2030-03",
            end_month="2030-03",
            cadence_months=1,
            lifecycle_status="active",
            end_profile_month=None,
            recurring_type="Fixed recurring",
        )
        missing = assess_recurring_series(
            {"2030-01": 100},
            period="month",
            start_month="2030-04",
            end_month="2030-04",
            cadence_months=1,
            lifecycle_status="active",
            end_profile_month=None,
            recurring_type="Fixed recurring",
        )

        self.assertEqual(expected.status, "expected")
        self.assertEqual(missing.status, "missing")

    def test_annual_series_appears_only_near_or_after_due_month(self) -> None:
        amounts = {"2029-06": 1200}
        hidden = assess_recurring_series(
            amounts,
            period="month",
            start_month="2030-04",
            end_month="2030-04",
            cadence_months=12,
            lifecycle_status="active",
            end_profile_month=None,
            recurring_type="Scheduled obligation",
        )
        upcoming = assess_recurring_series(
            amounts,
            period="month",
            start_month="2030-05",
            end_month="2030-05",
            cadence_months=12,
            lifecycle_status="active",
            end_profile_month=None,
            recurring_type="Scheduled obligation",
        )
        due = assess_recurring_series(
            amounts,
            period="month",
            start_month="2030-06",
            end_month="2030-06",
            cadence_months=12,
            lifecycle_status="active",
            end_profile_month=None,
            recurring_type="Scheduled obligation",
        )

        self.assertIsNone(hidden)
        self.assertEqual(upcoming.status, "upcoming")
        self.assertEqual(due.status, "due")

    def test_ended_profile_is_hidden_after_its_end_month(self) -> None:
        assessment = assess_recurring_series(
            {"2030-01": 100, "2030-02": 100},
            period="month",
            start_month="2030-03",
            end_month="2030-03",
            cadence_months=1,
            lifecycle_status="ended",
            end_profile_month="2030-02",
            recurring_type="Fixed recurring",
        )

        self.assertIsNone(assessment)

    def test_history_does_not_mark_months_after_end_as_missing(self) -> None:
        history = month_history(
            {"2030-01": 100, "2030-02": 100},
            "2030-04",
            1,
            "ended",
            "2030-02",
        )

        self.assertEqual(history[-1], {
            "month": "2030-04", "amount": None, "state": "not_expected"
        })
        self.assertEqual(median([10, 30, 20, 40]), 25)


if __name__ == "__main__":
    unittest.main()
