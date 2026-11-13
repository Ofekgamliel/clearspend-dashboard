from __future__ import annotations

import unittest

from clearspend.observations.monthly_analysis import (
    MonthlyDuplicateFinding,
    MonthlyObservationAnalysis,
    MonthlyObservationDataset,
    MonthlyObservationTransaction,
    MonthlyPurchaseFinding,
    MonthlyRecurringFinding,
)
from clearspend.observations.monthly_presentation import (
    monthly_findings,
    monthly_observation_groups,
)
from clearspend.observations.monthly_rules import (
    AmountLeftSignal,
    CategorySpendingSignal,
    HouseholdMonth,
)
from clearspend.observations.recurring_amount_rules import RecurringAmountSignal
from clearspend.observations.recurring_cycle_rules import AdditionalRecurringChargeSignal
from clearspend.observations.transaction_rules import (
    DuplicateCandidate,
    PurchaseSignal,
    StablePurchaseBaseline,
)


MONTH = "2030-04"


def transaction(
    transaction_id: int,
    *,
    amount: float = 100,
    date: str = "2030-04-10",
    event_name: str = "",
    original_amount: float | None = None,
    original_currency: str | None = None,
) -> MonthlyObservationTransaction:
    return MonthlyObservationTransaction(
        id=transaction_id,
        report_month=MONTH,
        merchant_raw="Synthetic Branch",
        merchant_normalized="synthetic branch",
        merchant_display_name="Synthetic Merchant",
        canonical_merchant_id="synthetic-id",
        category="Synthetic category",
        provider="synthetic",
        card_last4="0001",
        transaction_date=date,
        charged_amount=amount,
        charged_currency="ILS",
        personal_amount=amount,
        original_amount=original_amount,
        original_currency=original_currency,
        event_name=event_name,
    )


def dataset(*rows: MonthlyObservationTransaction) -> MonthlyObservationDataset:
    return MonthlyObservationDataset(
        MONTH,
        ("2030-01", "2030-02", "2030-03", MONTH),
        rows,
    )


class MonthlyObservationPresentationTests(unittest.TestCase):
    def test_amount_left_content_and_action_label_reach_single_card(self) -> None:
        signal = AmountLeftSignal(
            month=MONTH,
            observation_type="AMOUNT LEFT DECREASED",
            income=10_000,
            spending=8_000,
            remaining=2_000,
            remaining_percentage=20,
            baseline_remaining=5_000,
            baseline_percentage=50,
            amount_drop=3_000,
            percentage_point_drop=30,
            overspent=False,
            comparison_months=("2030-03", "2030-02", "2030-01"),
        )
        source = MonthlyObservationDataset(
            MONTH,
            ("2030-01", "2030-02", "2030-03", MONTH),
            household_history={
                value: HouseholdMonth(value, 10_000, 5_000)
                for value in ("2030-01", "2030-02", "2030-03")
            },
        )
        groups = monthly_observation_groups(
            MonthlyObservationAnalysis(amount_left=signal), source,
        )
        self.assertEqual(groups[0].value, "₪2,000.00 · 20.0% left")
        self.assertEqual(groups[0].primary_label, "Review income & spending →")
        self.assertIn("Jan 2030 – Mar 2030", groups[0].items[0].comparison_detail)
        self.assertEqual(len(groups[0].items[0].evidence), 5)

    def test_duplicate_preserves_review_and_activity_metadata(self) -> None:
        rows = (
            transaction(1, event_name="Synthetic event"),
            transaction(2, event_name="Synthetic event"),
        )
        signal = DuplicateCandidate((1, 2), 100)
        analysis = MonthlyObservationAnalysis(possible_duplicates=(
            MonthlyDuplicateFinding("Synthetic Merchant", signal),
        ))
        finding = monthly_findings(analysis, dataset(*rows))[0]
        self.assertEqual(finding.finding_key, "POSSIBLE DUPLICATE:1,2")
        self.assertEqual(finding.transaction_ids, (1, 2))
        self.assertEqual(finding.event_label, "Synthetic event")
        self.assertEqual(
            monthly_observation_groups(
                analysis, dataset(*rows), (finding.finding_key,),
            ),
            (),
        )

    def test_category_findings_use_compact_grouping(self) -> None:
        signals = tuple(
            CategorySpendingSignal(
                category=category,
                observation_type="CATEGORY SPENDING INCREASED",
                current_amount=2_000 + index * 100,
                routine_total=10_000,
                previous_amounts=(500, 500, 500),
                active_history_months=3,
                baseline=500,
                increase=1_500 + index * 100,
                ratio=4 + index / 5,
                routine_share=0.2,
            )
            for index, category in enumerate(("Food", "Travel"))
        )
        group = monthly_observation_groups(
            MonthlyObservationAnalysis(category_spending=signals), dataset(),
        )[0]
        self.assertEqual(group.title, "2 categories increased significantly")
        self.assertEqual(len(group.compact_categories), 2)
        self.assertTrue(all(item.month == MONTH for item in group.items))

    def test_foreign_recurring_amount_uses_original_currency_evidence(self) -> None:
        rows = (
            transaction(
                1, date="2030-02-10", amount=35,
                original_amount=10, original_currency="USD",
            ),
            transaction(
                2, date="2030-03-10", amount=36,
                original_amount=10, original_currency="USD",
            ),
            transaction(
                3, amount=44, original_amount=12, original_currency="USD",
            ),
        )
        signal = RecurringAmountSignal(
            observation_type="RECURRING AMOUNT INCREASED",
            transaction_id=3,
            recurring_type="Fixed recurring",
            observed_amount=12,
            comparison_currency="USD",
            baseline=10,
            observed_minimum=10,
            observed_maximum=10,
            increase_above_comparison=2,
            threshold=1,
            comparison_charge_ids=(1, 2),
            fixed=True,
        )
        finding = monthly_findings(MonthlyObservationAnalysis(
            recurring_findings=(MonthlyRecurringFinding(
                "Synthetic Service", "series-1", signal,
            ),),
        ), dataset(*rows))[0]
        self.assertEqual(finding.value, "USD 12.00")
        self.assertEqual(finding.comparison, "USD 10.00")
        self.assertIn("USD 10.00", finding.evidence[0])

    def test_additional_recurring_charge_keeps_series_and_occurrence(self) -> None:
        rows = (transaction(1), transaction(2, date="2030-04-12"))
        signal = AdditionalRecurringChargeSignal(
            observation_type="ADDITIONAL RECURRING CHARGE",
            recurring_series_id="series-1",
            expected_date="2030-04-10",
            transaction_ids=(1, 2),
            occurrence_start="2030-04-10",
            occurrence_end="2030-04-12",
            charge_count=2,
            additional_count=1,
            total_amount=200,
            learned_days=(10, 10, 10),
            finding_key="ADDITIONAL RECURRING CHARGE:series-1:2030-04-10:1,2",
        )
        finding = monthly_findings(MonthlyObservationAnalysis(
            recurring_findings=(MonthlyRecurringFinding(
                "Synthetic Merchant", "series-1", signal,
            ),),
        ), dataset(*rows))[0]
        self.assertEqual(finding.recurring_series_id, "series-1")
        self.assertEqual(finding.occurrence_end, "2030-04-12")
        self.assertEqual(finding.transaction_ids, (1, 2))

    def test_unusual_purchase_is_reviewable_but_combined_purchase_is_factual(self) -> None:
        baseline = StablePurchaseBaseline(100, 5, 3, 4)
        unusual = PurchaseSignal(
            1, "UNUSUAL TRANSACTION", 300, 5_000, 0.06, baseline, 3,
        )
        combined = PurchaseSignal(
            2, "LARGE AND UNUSUAL PURCHASE", 600, 5_000, 0.12, baseline, 6,
        )
        findings = monthly_findings(MonthlyObservationAnalysis(purchases=(
            MonthlyPurchaseFinding("First", unusual),
            MonthlyPurchaseFinding("Second", combined),
        )), dataset(transaction(1, amount=300), transaction(2, amount=600)))
        self.assertEqual(findings[0].finding_key, "UNUSUAL TRANSACTION:1")
        self.assertEqual(findings[0].transaction_ids, (1,))
        self.assertEqual(findings[1].finding_key, "")
        self.assertEqual(findings[1].transaction_ids, ())

    def test_large_purchase_with_history_is_not_described_as_unusual(self) -> None:
        baseline = StablePurchaseBaseline(400, 5, 3, 4)
        large = PurchaseSignal(
            1, "LARGE PURCHASE", 600, 5_000, 0.12, baseline, 1.5,
        )
        finding = monthly_findings(MonthlyObservationAnalysis(purchases=(
            MonthlyPurchaseFinding("Synthetic Merchant", large),
        )), dataset(transaction(1, amount=600)))[0]
        self.assertIn("monthly personal spending", finding.comparison)
        self.assertIn("12.0% of month", finding.result)
        self.assertNotIn("median", finding.result)

    def test_monthly_groups_keep_established_priority(self) -> None:
        duplicate = MonthlyDuplicateFinding(
            "Duplicate", DuplicateCandidate((1, 2), 100),
        )
        purchase = MonthlyPurchaseFinding(
            "Large",
            PurchaseSignal(3, "LARGE PURCHASE", 600, 5_000, 0.12, None, 0),
        )
        groups = monthly_observation_groups(
            MonthlyObservationAnalysis(
                possible_duplicates=(duplicate,), purchases=(purchase,),
            ),
            dataset(transaction(1), transaction(2), transaction(3, amount=600)),
        )
        self.assertEqual(tuple(group.observation_type for group in groups), (
            "POSSIBLE DUPLICATE", "LARGE PURCHASE",
        ))


if __name__ == "__main__":
    unittest.main()
