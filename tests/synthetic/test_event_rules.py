from __future__ import annotations

import unittest

from clearspend.events.rules import summarize_event_transactions, validate_event_settings


class EventRuleTests(unittest.TestCase):
    def test_regular_event_discards_destination_and_normalizes_values(self) -> None:
        settings = validate_event_settings(
            name="  Synthetic holiday  ",
            event_type=" trip ",
            destination="Not persisted",
            start_date="2030-04-01",
            end_date="2030-04-03",
            budget="1200.567",
            status=" completed ",
        )

        self.assertEqual(settings.name, "Synthetic holiday")
        self.assertEqual(settings.destination, "")
        self.assertEqual(settings.budget, 1200.57)

    def test_business_trip_requires_and_preserves_destination(self) -> None:
        with self.assertRaisesRegex(ValueError, "Destination is required"):
            validate_event_settings(
                name="Synthetic work trip", event_type="business_trip", destination="",
                start_date="2030-04-01", end_date="2030-04-03", budget="", status="planned",
            )

        settings = validate_event_settings(
            name="Synthetic work trip", event_type="business_trip", destination="Test City",
            start_date="2030-04-01", end_date="2030-04-03", budget="", status="planned",
        )
        self.assertEqual(settings.destination, "Test City")

    def test_cancelled_status_is_only_available_when_editing(self) -> None:
        arguments = dict(
            name="Synthetic event", event_type="other", start_date="2030-04-01",
            end_date="2030-04-01", budget=None, status="cancelled",
        )
        with self.assertRaisesRegex(ValueError, "Invalid event status"):
            validate_event_settings(**arguments)
        self.assertEqual(
            validate_event_settings(**arguments, allow_cancelled=True).status, "cancelled"
        )

    def test_invalid_dates_and_budget_are_rejected(self) -> None:
        base = dict(
            name="Synthetic event", event_type="other", start_date="2030-04-02",
            end_date="2030-04-01", budget="", status="active",
        )
        with self.assertRaisesRegex(ValueError, "End date cannot"):
            validate_event_settings(**base)
        with self.assertRaisesRegex(ValueError, "Budget cannot be negative"):
            validate_event_settings(**{**base, "end_date": "2030-04-03", "budget": -1})

    def test_summary_separates_period_and_lifetime_totals(self) -> None:
        rows = [
            {"transaction_date": "2030-03-31", "personal_amount": 20, "category": "Travel",
             "provider": "synthetic", "card_last4": "1111"},
            {"transaction_date": "2030-04-01", "personal_amount": 100, "category": "Travel",
             "provider": "synthetic", "card_last4": "1111"},
            {"transaction_date": "2030-04-02", "personal_amount": 40, "category": "Food",
             "provider": "synthetic", "card_last4": "2222"},
        ]

        summary = summarize_event_transactions(
            rows, period_start="2030-04-01", period_end="2030-04-30"
        )

        self.assertEqual(summary.transaction_count, 2)
        self.assertEqual(summary.amount, 140)
        self.assertEqual(summary.total_transaction_count, 3)
        self.assertEqual(summary.total_amount, 160)
        self.assertEqual(summary.category_count, 2)
        self.assertEqual(summary.card_count, 2)
