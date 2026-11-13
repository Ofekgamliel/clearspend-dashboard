from __future__ import annotations

import unittest

from clearspend.observations.historical_inputs import (
    analyze_historical_snapshot,
    historical_dataset_from_snapshot,
)
from clearspend.observations.inputs import ObservationInputSnapshot
from clearspend.observations.scope import ObservationScope


def historical_scope() -> ObservationScope:
    return ObservationScope(
        period="latest",
        selected_month="",
        scope_start="2030-01",
        scope_end="2030-03",
        target_months=("2030-01", "2030-02", "2030-03"),
        history_months=("2029-12", "2030-01", "2030-02", "2030-03"),
        recurring_months=("2029-12", "2030-01", "2030-02", "2030-03"),
        observed_start="2030-01",
        observed_end="2030-03",
    )


def snapshot(**overrides) -> ObservationInputSnapshot:
    values = {
        "scope": historical_scope(),
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


class HistoricalObservationInputAdapterTests(unittest.TestCase):
    def test_reporting_and_purchase_months_are_kept_separate(self) -> None:
        dataset = historical_dataset_from_snapshot(snapshot(
            transactions_by_month={
                "2030-02": ({
                    "id": 1,
                    "canonical_merchant_id": "synthetic-id",
                    "merchant_normalized": "synthetic merchant",
                    "merchant_display_name": "Synthetic Merchant",
                    "merchant_raw": "Synthetic Merchant Branch",
                    "transaction_date": "2030-01-29",
                    "personal_amount": 125,
                    "category": "Synthetic category",
                    "installment_total": None,
                    "event_id": 7,
                },),
            },
        ))
        self.assertEqual(dataset.routine_transactions[0].month, "2030-02")
        self.assertEqual(dataset.routine_transactions[0].event_id, 7)
        self.assertEqual(dataset.merchant_transactions[0].purchase_month, "2030-01")
        self.assertEqual(
            dataset.merchant_transactions[0].identity,
            "synthetic-id\0Synthetic category",
        )

    def test_text_event_id_remains_assigned(self) -> None:
        dataset = historical_dataset_from_snapshot(snapshot(
            transactions_by_month={
                "2030-01": ({
                    "merchant_raw": "Synthetic Store",
                    "transaction_date": "2030-01-05",
                    "personal_amount": 500,
                    "event_id": "synthetic-trip-2030",
                },),
            },
        ))
        self.assertEqual(
            dataset.routine_transactions[0].event_id,
            "synthetic-trip-2030",
        )
        self.assertEqual(
            dataset.merchant_transactions[0].event_id,
            "synthetic-trip-2030",
        )

    def test_household_rows_and_visibility_are_normalized(self) -> None:
        dataset = historical_dataset_from_snapshot(snapshot(
            income_visible=False,
            partial_month="2030-03",
            household_history={
                "2030-02": {"bucket": "2030-02", "income": 1_000, "amount": 600},
            },
        ))
        row = dataset.household_history["2030-02"]
        self.assertEqual((row.income, row.spending), (1_000, 600))
        self.assertFalse(dataset.income_visible)
        self.assertEqual(dataset.partial_month, "2030-03")

    def test_recurring_aliases_lifecycle_and_installments_are_preserved(self) -> None:
        recurring_by_month = {
            month: {
                "metrics": {"active_series": 1, "installment_billed": 250},
                "series": [{
                    "series_id": "synthetic-series",
                    "amount": 120,
                    "cadence": "Monthly",
                    "lifecycle_status": "active",
                    "status": "confirmed",
                    "display_name": "Synthetic Service",
                    "source_aliases": ["Synthetic Service Branch"],
                }],
                "commitments": [{
                    "display_name": "Synthetic Plan",
                    "source_alias": "Synthetic Plan Branch",
                    "total_installments": 6,
                }],
            }
            for month in historical_scope().recurring_months
        }
        dataset = historical_dataset_from_snapshot(snapshot(
            recurring_by_month=recurring_by_month,
        ))
        recurring = dataset.recurring_history["2030-01"]
        installment = dataset.installment_history["2030-01"]
        self.assertEqual(recurring.series[0].status, "active")
        self.assertEqual(recurring.active_series_count, 1)
        self.assertEqual(dataset.recurring_aliases, ("Synthetic Service Branch",))
        self.assertEqual(installment.installment_billed, 250)
        self.assertIn("Synthetic Plan Branch", installment.commitments[0].identity)

    def test_dedicated_installment_identity_takes_priority_over_public_payload(self) -> None:
        recurring_by_month = {
            month: {
                "metrics": {"installment_billed": 999},
                "series": [],
                "commitments": [{"display_name": "Public fallback"}],
            }
            for month in historical_scope().recurring_months
        }
        installments_by_month = {
            month: {
                "installment_billed": 150,
                "plans": ({
                    "plan_id": f"stable-{month}",
                    "display_name": "Stable plan",
                    "source_alias": "Stable plan branch",
                    "original_purchase_date": "2029-12-15",
                    "original_amount": "900.00",
                    "installment_total": 6,
                },),
            }
            for month in historical_scope().recurring_months
        }
        dataset = historical_dataset_from_snapshot(snapshot(
            recurring_by_month=recurring_by_month,
            installments_by_month=installments_by_month,
        ))
        installment = dataset.installment_history["2030-01"]
        self.assertEqual(installment.installment_billed, 150)
        self.assertEqual(installment.commitments[0].identity, "stable-2030-01")

    def test_month_snapshot_is_rejected_before_analysis(self) -> None:
        month_scope = ObservationScope(
            period="month",
            selected_month="2030-03",
            scope_start="2030-03",
            scope_end="2030-03",
            target_months=("2030-03",),
            history_months=("2030-03",),
            recurring_months=("2030-03",),
            observed_start="2030-03",
            observed_end="2030-03",
        )
        with self.assertRaisesRegex(ValueError, "requires a long period"):
            historical_dataset_from_snapshot(snapshot(scope=month_scope))

    def test_adapter_and_coordinator_can_run_as_one_read_only_boundary(self) -> None:
        analysis = analyze_historical_snapshot(snapshot())
        self.assertEqual(analysis.signals, ())


if __name__ == "__main__":
    unittest.main()
