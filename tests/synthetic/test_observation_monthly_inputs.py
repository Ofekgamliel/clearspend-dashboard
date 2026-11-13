from __future__ import annotations

import unittest

from clearspend.observations.inputs import ObservationInputSnapshot
from clearspend.observations.monthly_inputs import (
    analyze_monthly_snapshot,
    monthly_dataset_from_snapshot,
)
from clearspend.observations.scope import ObservationScope


def month_scope() -> ObservationScope:
    return ObservationScope(
        period="month",
        selected_month="2030-03",
        scope_start="2030-03",
        scope_end="2030-03",
        target_months=("2030-03",),
        history_months=("2030-01", "2030-02", "2030-03"),
        recurring_months=("2030-03",),
        observed_start="2030-03",
        observed_end="2030-03",
    )


def snapshot(**overrides) -> ObservationInputSnapshot:
    values = {
        "scope": month_scope(),
        "selected_card": "all",
        "income_visible": True,
        "partial_month": "",
        "dashboard": {},
        "transactions_by_month": {},
        "recurring_by_month": {},
        "household_history": {},
        "reviewed_finding_keys": frozenset(),
        "installments_by_month": {},
    }
    values.update(overrides)
    return ObservationInputSnapshot(**values)


class MonthlyObservationInputAdapterTests(unittest.TestCase):
    def test_transaction_fields_and_reporting_month_are_normalized(self) -> None:
        dataset = monthly_dataset_from_snapshot(snapshot(
            transactions_by_month={
                "2030-02": ({
                    "id": "7",
                    "merchant_raw": "Synthetic Branch",
                    "merchant_normalized": "synthetic branch",
                    "merchant_display_name": "Synthetic Merchant",
                    "canonical_merchant_id": "synthetic-id",
                    "category": "Synthetic category",
                    "provider": "synthetic",
                    "card_last4": "0001",
                    "transaction_date": "2030-01-29",
                    "amount": "125.50",
                    "charged_currency": "ILS",
                    "personal_amount": "100.25",
                    "original_amount": "40",
                    "original_currency": "USD",
                    "installment_total": "3",
                    "event_id": "9",
                    "event_name": "Synthetic event",
                    "notes": "Synthetic note",
                },),
            },
        ))
        transaction = dataset.transactions[0]
        self.assertEqual(transaction.id, 7)
        self.assertEqual(transaction.report_month, "2030-02")
        self.assertEqual(transaction.transaction_date, "2030-01-29")
        self.assertEqual(transaction.charged_amount, 125.50)
        self.assertEqual(transaction.personal_amount, 100.25)
        self.assertEqual(transaction.original_amount, 40)
        self.assertEqual(transaction.installment_total, 3)
        self.assertEqual(transaction.event_id, 9)
        self.assertEqual(transaction.event_name, "Synthetic event")

    def test_text_event_id_is_preserved(self) -> None:
        dataset = monthly_dataset_from_snapshot(snapshot(
            transactions_by_month={
                "2030-03": ({
                    "id": 10,
                    "merchant_raw": "Synthetic Store",
                    "transaction_date": "2030-03-05",
                    "personal_amount": 100,
                    "event_id": "synthetic-event-2030",
                },),
            },
        ))
        self.assertEqual(
            dataset.transactions[0].event_id,
            "synthetic-event-2030",
        )

    def test_missing_purchase_date_uses_billing_date_then_reporting_month(self) -> None:
        dataset = monthly_dataset_from_snapshot(snapshot(
            transactions_by_month={
                "2030-01": (
                    {"id": 1, "billing_date": "2030-01-12"},
                    {"id": 2},
                ),
            },
        ))
        self.assertEqual(
            tuple(row.transaction_date for row in dataset.transactions),
            ("2030-01-12", "2030-01-01"),
        )

    def test_null_personal_amount_falls_back_to_card_charge(self) -> None:
        dataset = monthly_dataset_from_snapshot(snapshot(
            transactions_by_month={
                "2030-03": ({
                    "id": 1,
                    "amount": "75.25",
                    "personal_amount": None,
                },),
            },
        ))
        self.assertEqual(dataset.transactions[0].personal_amount, 75.25)

    def test_recurring_profile_uses_target_month_alias_and_category(self) -> None:
        dataset = monthly_dataset_from_snapshot(snapshot(
            recurring_by_month={
                "2030-03": {
                    "series": ({
                        "series_id": "synthetic-series",
                        "display_name": "Synthetic Service",
                        "category": "Subscriptions",
                        "recurring_type": "Fixed recurring",
                        "cadence": "Monthly",
                        "source_aliases": ["Synthetic Branch"],
                    },),
                },
            },
        ))
        series = dataset.recurring_series[0]
        self.assertEqual(series.series_id, "synthetic-series")
        self.assertEqual(series.category, "Subscriptions")
        self.assertEqual(series.source_aliases, ("Synthetic Branch",))

    def test_household_visibility_and_partial_month_are_preserved(self) -> None:
        dataset = monthly_dataset_from_snapshot(snapshot(
            income_visible=False,
            partial_month="2030-03",
            household_history={
                "2030-02": {"income": "1000", "amount": "600"},
            },
        ))
        self.assertFalse(dataset.income_visible)
        self.assertEqual(dataset.partial_month, "2030-03")
        self.assertEqual(dataset.household_history["2030-02"].remaining, 400)

    def test_invalid_transaction_ids_are_not_adapted(self) -> None:
        dataset = monthly_dataset_from_snapshot(snapshot(
            transactions_by_month={"2030-03": ({"id": "not-an-id"},)},
        ))
        self.assertEqual(dataset.transactions, ())

    def test_long_period_snapshot_is_rejected(self) -> None:
        scope = month_scope()
        historical = ObservationScope(
            period="latest",
            selected_month="",
            scope_start="2030-01",
            scope_end="2030-03",
            target_months=("2030-01", "2030-02", "2030-03"),
            history_months=scope.history_months,
            recurring_months=scope.history_months,
            observed_start="2030-01",
            observed_end="2030-03",
        )
        with self.assertRaisesRegex(ValueError, "requires a month period"):
            monthly_dataset_from_snapshot(snapshot(scope=historical))

    def test_adapter_and_coordinator_run_as_one_read_only_boundary(self) -> None:
        analysis = analyze_monthly_snapshot(snapshot())
        self.assertEqual(analysis.signals, ())


if __name__ == "__main__":
    unittest.main()
