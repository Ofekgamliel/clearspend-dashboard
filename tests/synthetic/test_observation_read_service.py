from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from clearspend.observations.grouping import ObservationFinding, ObservationGroup
from clearspend.observations.inputs import ObservationInputSnapshot
from clearspend.observations.payloads import (
    finding_payload,
    observation_view_payload,
    observations_payload,
)
from clearspend.observations.read_service import (
    ObservationView,
    observation_view_from_snapshot,
)
from clearspend.observations.scope import ObservationScope
from tests.synthetic.support import add_import, add_transaction, connect, create_database


def scope(period: str = "month") -> ObservationScope:
    historical = period != "month"
    return ObservationScope(
        period=period,
        selected_month="" if historical else "2030-03",
        scope_start="2030-01" if historical else "2030-03",
        scope_end="2030-03",
        target_months=("2030-01", "2030-02", "2030-03") if historical else ("2030-03",),
        history_months=("2030-01", "2030-02", "2030-03"),
        recurring_months=("2030-01", "2030-02", "2030-03") if historical else ("2030-03",),
        observed_start="2030-01" if historical else "2030-03",
        observed_end="2030-03",
    )


def snapshot(**overrides) -> ObservationInputSnapshot:
    values = {
        "scope": scope(),
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


def duplicate_rows() -> dict[str, tuple[dict, ...]]:
    base = {
        "merchant_raw": "Synthetic Store",
        "merchant_normalized": "synthetic store",
        "merchant_display_name": "Synthetic Store",
        "canonical_merchant_id": "synthetic-store",
        "category": "Shopping",
        "provider": "synthetic",
        "card_last4": "0001",
        "transaction_date": "2030-03-10",
        "amount": 100,
        "charged_currency": "ILS",
        "personal_amount": 100,
    }
    return {"2030-03": ({**base, "id": 1}, {**base, "id": 2})}


class ObservationReadServiceTests(unittest.TestCase):
    def test_monthly_snapshot_uses_monthly_analysis_and_grouping(self) -> None:
        view = observation_view_from_snapshot(snapshot(
            transactions_by_month=duplicate_rows(),
        ))
        self.assertFalse(view.historical)
        self.assertEqual(view.finding_count, 1)
        self.assertEqual(view.type_count, 1)
        self.assertEqual(view.findings[0].observation_type, "POSSIBLE DUPLICATE")
        self.assertEqual(view.groups[0].items, view.findings)

    def test_review_state_is_applied_to_findings_and_groups(self) -> None:
        view = observation_view_from_snapshot(snapshot(
            transactions_by_month=duplicate_rows(),
            reviewed_finding_keys=frozenset({"POSSIBLE DUPLICATE:1,2"}),
        ))
        self.assertEqual(view.findings, ())
        self.assertEqual(view.groups, ())

    def test_long_period_snapshot_uses_historical_boundary(self) -> None:
        view = observation_view_from_snapshot(snapshot(scope=scope("year")))
        self.assertTrue(view.historical)
        self.assertEqual(view.period, "year")
        self.assertEqual((view.observed_start, view.observed_end), ("2030-01", "2030-03"))
        self.assertEqual(view.findings, ())

    def test_finding_serializer_preserves_review_and_card_metadata(self) -> None:
        finding = ObservationFinding(
            observation_type="POSSIBLE DUPLICATE",
            month="2030-03",
            label="Synthetic Store",
            title="Matching charges",
            description="Synthetic description",
            score=200,
            value="2 × ₪100.00",
            comparison="Exact match",
            result="2 candidates",
            finding_key="POSSIBLE DUPLICATE:1,2",
            transaction_ids=(1, 2),
            event_label="Synthetic event",
            card_comparison_primary="Primary",
            card_comparison_secondary="Secondary",
        )
        payload = finding_payload(finding)
        self.assertEqual(payload["type"], "POSSIBLE DUPLICATE")
        self.assertEqual(payload["transactionIds"], [1, 2])
        self.assertEqual(payload["findingKey"], "POSSIBLE DUPLICATE:1,2")
        self.assertEqual(payload["cardComparison"]["primary"], "Primary")
        self.assertNotIn("comparisonDetail", payload)

    def test_single_group_preserves_card_comparison_for_frontend_rendering(self) -> None:
        finding = ObservationFinding(
            observation_type="SPENDING ROUTINE SHIFTED",
            label="Overall spending",
            title="Synthetic shift",
            description="Synthetic description",
            card_comparison_primary="Recent versus baseline",
            card_comparison_secondary="Synthetic change",
        )
        # Exercise the actual grouping path rather than constructing a group by hand.
        from clearspend.observations.grouping import group_observation_findings
        view = ObservationView(
            "year", "all", "", "2030-01", "2030-03", (finding,),
            group_observation_findings((finding,)),
        )
        group = observation_view_payload(view)["groups"][0]
        self.assertEqual(group["cardComparison"]["primary"], "Recent versus baseline")

    def test_view_serializer_exposes_stable_counts_and_browser_field_names(self) -> None:
        finding = ObservationFinding(
            "LARGE PURCHASE", "Synthetic", "Large", "Description",
        )
        group = ObservationGroup(
            "LARGE PURCHASE", (finding,), "Large", "Description", "", "", "",
        )
        payload = observation_view_payload(ObservationView(
            "month", "all", "2030-03", "2030-03", "2030-03", (finding,), (group,),
        ))
        self.assertEqual(payload["findingCount"], 1)
        self.assertEqual(payload["typeCount"], 1)
        self.assertEqual(payload["selectedCard"], "all")
        self.assertEqual(payload["groups"][0]["cardSummary"], "")

    def test_database_payload_is_read_only_and_not_routed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "synthetic.db"
            create_database(database)
            connection = connect(database)
            import_id = add_import(connection)
            for index in range(2):
                add_transaction(
                    connection,
                    import_id,
                    key=f"duplicate-{index}",
                    merchant="Synthetic Store",
                    amount=100,
                    category="Shopping",
                    transaction_date="2030-03-10",
                    billing_month="2030-03",
                )
            connection.commit()
            connection.close()

            payload = observations_payload(
                database, period="month", card="all", month="2030-03",
            )

            self.assertEqual(payload["findingCount"], 1)
            self.assertEqual(payload["findings"][0]["type"], "POSSIBLE DUPLICATE")
            verify = connect(database)
            try:
                self.assertEqual(
                    verify.execute("SELECT COUNT(*) FROM observation_reviews").fetchone()[0],
                    0,
                )
            finally:
                verify.close()


if __name__ == "__main__":
    unittest.main()
