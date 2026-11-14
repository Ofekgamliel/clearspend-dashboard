from __future__ import annotations

import unittest
from datetime import date

from clearspend.reporting.periods import add_months, month_number, resolve_period, shift_month


class ReportingPeriodTests(unittest.TestCase):
    def test_month_defaults_to_latest_non_future_coverage(self) -> None:
        selection = resolve_period(
            "month",
            earliest=date(2029, 1, 1),
            latest=date(2031, 2, 1),
            latest_available_month=date(2030, 11, 1),
        )

        self.assertEqual(selection.start, date(2030, 11, 1))
        self.assertEqual(selection.end, date(2030, 11, 30))
        self.assertEqual(selection.label, "November 2030")

    def test_requested_month_can_select_future_coverage(self) -> None:
        selection = resolve_period(
            "month",
            earliest=date(2029, 1, 1),
            latest=date(2031, 2, 1),
            latest_available_month=date(2030, 11, 1),
            requested_month="2031-02",
        )

        self.assertEqual(selection.start, date(2031, 2, 1))
        self.assertEqual(selection.end, date(2031, 2, 28))

    def test_invalid_requested_month_falls_back_to_default(self) -> None:
        selection = resolve_period(
            "month",
            earliest=date(2030, 1, 1),
            latest=date(2030, 6, 1),
            latest_available_month=date(2030, 5, 1),
            requested_month="not-a-month",
        )

        self.assertEqual(selection.start, date(2030, 5, 1))

    def test_year_uses_calendar_year_of_latest_coverage(self) -> None:
        selection = resolve_period(
            "year",
            earliest=date(2028, 3, 1),
            latest=date(2030, 8, 1),
        )

        self.assertEqual(selection.start, date(2030, 1, 1))
        self.assertEqual(selection.end, date(2030, 12, 31))
        self.assertEqual(selection.label, "2030")

    def test_all_time_uses_complete_coverage(self) -> None:
        selection = resolve_period(
            "all",
            earliest=date(2028, 3, 1),
            latest=date(2030, 8, 1),
        )

        self.assertEqual(selection.start, date(2028, 3, 1))
        self.assertEqual(selection.end, date(2030, 8, 1))
        self.assertEqual(selection.label, "Mar 2028 – Aug 2030")

    def test_empty_coverage_has_no_bounds(self) -> None:
        selection = resolve_period("month", earliest=None, latest=None)

        self.assertIsNone(selection.start)
        self.assertIsNone(selection.end)
        self.assertEqual(selection.label, "No transactions")

    def test_month_arithmetic_crosses_year_boundaries(self) -> None:
        self.assertEqual(add_months(date(2030, 12, 19), 1), date(2031, 1, 1))
        self.assertEqual(shift_month("2030-01", -1), "2029-12")
        self.assertEqual(month_number("2031-01") - month_number("2030-01"), 12)


if __name__ == "__main__":
    unittest.main()
