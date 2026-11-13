from __future__ import annotations

import unittest

from clearspend.reporting.scope import build_reporting_filter


MONTH_SQL = "COALESCE(billing_month,substr(transaction_date,1,7))"


class ReportingScopeTests(unittest.TestCase):
    def test_all_cards_and_all_spending(self) -> None:
        result = build_reporting_filter(
            MONTH_SQL, start="2026-01-01", end="2026-12-31", card="all"
        )

        self.assertEqual(result.where, f"{MONTH_SQL} BETWEEN ? AND ?")
        self.assertEqual(result.parameters, ("2026-01", "2026-12"))

    def test_selected_card_adds_provider_and_last_four(self) -> None:
        result = build_reporting_filter(
            MONTH_SQL, start="2030-06-01", end="2030-06-30", card="synthetic:0001"
        )

        self.assertEqual(
            result.where,
            f"{MONTH_SQL} BETWEEN ? AND ? AND provider = ? AND card_last4 = ?",
        )
        self.assertEqual(
            result.parameters,
            ("2030-06", "2030-06", "synthetic", "0001"),
        )

    def test_routine_scope_excludes_event_transactions(self) -> None:
        result = build_reporting_filter(
            MONTH_SQL,
            start="2026-06-01",
            end="2026-06-30",
            card="all",
            event_scope="routine",
        )

        self.assertEqual(
            result.where,
            f"{MONTH_SQL} BETWEEN ? AND ? AND NOT EXISTS "
            "(SELECT 1 FROM event_transactions scoped_event "
            "WHERE scoped_event.transaction_id=t.id)",
        )

    def test_open_bounds_and_malformed_card_preserve_existing_behavior(self) -> None:
        result = build_reporting_filter(
            MONTH_SQL, start=None, end=None, card="synthetic-0001"
        )

        self.assertEqual(result.parameters, ("0000-00", "9999-99"))
        self.assertNotIn("provider", result.where)

    def test_invalid_event_scope_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "Invalid event scope"):
            build_reporting_filter(
                MONTH_SQL, start="2026-01-01", end="2026-01-31", card="all", event_scope="events"
            )
