from __future__ import annotations

import unittest
import shutil

from clearspend.observations.inputs import ObservationInputSnapshot
from clearspend.observations.parity import compare_observation_payloads
from clearspend.observations.payloads import observation_view_payload
from clearspend.observations.read_service import observation_view_from_snapshot
from clearspend.observations.scope import ObservationScope
from tests.synthetic.observation_parity_support import browser_observation_payload


def scope(period: str = "month") -> ObservationScope:
    historical = period != "month"
    return ObservationScope(
        period=period,
        selected_month="" if historical else "2030-04",
        scope_start="2030-01" if historical else "2030-04",
        scope_end="2030-04",
        target_months=("2030-01", "2030-02", "2030-03", "2030-04") if historical else ("2030-04",),
        history_months=("2030-01", "2030-02", "2030-03", "2030-04"),
        recurring_months=("2030-01", "2030-02", "2030-03", "2030-04") if historical else ("2030-04",),
        observed_start="2030-01" if historical else "2030-04",
        observed_end="2030-04",
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


def backend_payload(value: ObservationInputSnapshot) -> dict:
    return observation_view_payload(observation_view_from_snapshot(value))


def duplicate_rows() -> dict[str, tuple[dict, ...]]:
    base = {
        "merchant_raw": "Synthetic Store",
        "merchant_normalized": "synthetic store",
        "merchant_display_name": "Synthetic Store",
        "canonical_merchant_id": "synthetic-store",
        "category": "Shopping",
        "provider": "synthetic",
        "card_last4": "0001",
        "transaction_date": "2030-04-10",
        "amount": 100,
        "charged_currency": "ILS",
        "personal_amount": 100,
    }
    return {"2030-04": ({**base, "id": 1}, {**base, "id": 2})}


@unittest.skipUnless(shutil.which("node"), "Node.js is required for browser parity")
class ObservationParityTests(unittest.TestCase):
    def test_empty_month_matches_at_all_three_tiers(self) -> None:
        value = snapshot()
        report = compare_observation_payloads(
            browser_observation_payload(value), backend_payload(value),
        )
        self.assertTrue(report.qualification_matches)
        self.assertTrue(report.grouping_matches)
        self.assertTrue(report.presentation_matches)

    def test_duplicate_qualification_grouping_and_review_suppression_match(self) -> None:
        value = snapshot(transactions_by_month=duplicate_rows())
        report = compare_observation_payloads(
            browser_observation_payload(value), backend_payload(value),
        )
        self.assertTrue(report.qualification_matches)
        self.assertTrue(report.grouping_matches)
        reviewed = snapshot(
            transactions_by_month=duplicate_rows(),
            reviewed_finding_keys=frozenset({"POSSIBLE DUPLICATE:1,2"}),
        )
        reviewed_report = compare_observation_payloads(
            browser_observation_payload(reviewed), backend_payload(reviewed),
        )
        self.assertTrue(reviewed_report.qualification_matches)
        self.assertTrue(reviewed_report.grouping_matches)
        self.assertEqual(reviewed_report.backend_finding_count, 0)

    def test_historical_empty_period_matches(self) -> None:
        value = snapshot(scope=scope("year"))
        report = compare_observation_payloads(
            browser_observation_payload(value), backend_payload(value),
        )
        self.assertTrue(report.qualification_matches)
        self.assertTrue(report.grouping_matches)

    def test_report_separates_qualification_from_presentation_differences(self) -> None:
        browser = {
            "findings": [{
                "type": "LARGE PURCHASE", "month": "2030-04", "label": "Store",
                "title": "Browser title", "value": "100",
            }],
            "groups": [{"type": "LARGE PURCHASE"}],
        }
        backend = {
            "findings": [{
                "type": "LARGE PURCHASE", "month": "2030-04", "label": "Store",
                "title": "Backend title", "value": "100",
            }],
            "groups": [{"type": "LARGE PURCHASE"}],
        }
        report = compare_observation_payloads(browser, backend)
        self.assertTrue(report.qualification_matches)
        self.assertTrue(report.grouping_matches)
        self.assertFalse(report.presentation_matches)


if __name__ == "__main__":
    unittest.main()
