from __future__ import annotations

import unittest

from clearspend.observations.monthly_analysis import (
    MonthlyObservationDataset,
    MonthlyObservationTransaction,
    MonthlyRecurringSeries,
    analyze_monthly_observations,
)
from clearspend.observations.monthly_rules import HouseholdMonth


MONTH = "2030-04"


def transaction(
    transaction_id: int,
    *,
    month: str = MONTH,
    day: int = 10,
    amount: float = 100,
    merchant: str = "synthetic merchant",
    category: str = "Synthetic category",
    event_id: int | None = None,
    notes: str = "",
    installment_total: int | None = None,
) -> MonthlyObservationTransaction:
    return MonthlyObservationTransaction(
        id=transaction_id,
        report_month=month,
        merchant_raw=merchant,
        merchant_normalized=merchant,
        merchant_display_name=merchant.title(),
        canonical_merchant_id=merchant,
        category=category,
        provider="synthetic",
        card_last4="0001",
        transaction_date=f"{month}-{day:02d}",
        charged_amount=amount,
        charged_currency="ILS",
        personal_amount=amount,
        installment_total=installment_total,
        notes=notes,
        event_id=event_id,
    )


class MonthlyObservationAnalysisTests(unittest.TestCase):
    def test_empty_dataset_returns_no_signals(self) -> None:
        analysis = analyze_monthly_observations(
            MonthlyObservationDataset(MONTH, (MONTH,)),
        )
        self.assertEqual(analysis.signals, ())

    def test_transactions_outside_declared_coverage_are_ignored(self) -> None:
        analysis = analyze_monthly_observations(MonthlyObservationDataset(
            MONTH,
            (MONTH,),
            (
                transaction(1, month="2030-05", amount=1_000),
                transaction(2, month="2030-05", amount=1_000),
            ),
        ))
        self.assertEqual(analysis.signals, ())

    def test_partial_month_suppresses_household_and_category_only(self) -> None:
        rows = tuple(
            transaction(index, month=month, amount=500)
            for index, month in enumerate(
                ("2030-01", "2030-02", "2030-03"), start=1,
            )
        ) + (
            transaction(10, amount=2_000),
            transaction(11, amount=2_000),
        )
        household = {
            month: HouseholdMonth(month, 10_000, 5_000)
            for month in ("2030-01", "2030-02", "2030-03")
        }
        household[MONTH] = HouseholdMonth(MONTH, 10_000, 11_000)
        analysis = analyze_monthly_observations(MonthlyObservationDataset(
            MONTH,
            ("2030-01", "2030-02", "2030-03", MONTH),
            rows,
            household_history=household,
            partial_month=MONTH,
            income_visible=True,
        ))
        self.assertIsNone(analysis.amount_left)
        self.assertEqual(analysis.category_spending, ())
        self.assertEqual(len(analysis.possible_duplicates), 1)

    def test_category_routine_excludes_events_but_monthly_share_keeps_them(self) -> None:
        rows = []
        for index, month in enumerate(("2030-01", "2030-02", "2030-03"), start=1):
            rows.append(transaction(index, month=month, amount=1_000))
        rows.extend((
            transaction(10, amount=2_000),
            transaction(11, amount=8_000, merchant="event", event_id=7),
        ))
        analysis = analyze_monthly_observations(MonthlyObservationDataset(
            MONTH,
            ("2030-01", "2030-02", "2030-03", MONTH),
            tuple(rows),
        ))
        self.assertEqual(len(analysis.category_spending), 1)
        purchase = next(
            finding for finding in analysis.purchases
            if finding.signal.transaction_id == 11
        )
        self.assertEqual(purchase.signal.monthly_total, 10_000)
        self.assertEqual(purchase.signal.monthly_share, 0.8)

    def test_reviewed_recurring_increase_is_not_a_generic_purchase_or_fee(self) -> None:
        rows = tuple(
            transaction(
                index,
                month=month,
                amount=100 if month != MONTH else 102,
                merchant="monthly fee",
                notes="fee",
            )
            for index, month in enumerate(
                ("2030-01", "2030-02", "2030-03", MONTH), start=1,
            )
        )
        series = MonthlyRecurringSeries(
            "series-1",
            "Monthly fee",
            "Synthetic category",
            "Fixed recurring",
            "Monthly",
            ("monthly fee",),
        )
        analysis = analyze_monthly_observations(MonthlyObservationDataset(
            MONTH,
            ("2030-01", "2030-02", "2030-03", MONTH),
            rows,
            (series,),
        ))
        self.assertEqual(analysis.recurring_transaction_ids, frozenset({4}))
        self.assertEqual(len(analysis.recurring_findings), 1)
        self.assertEqual(
            analysis.recurring_findings[0].signal.observation_type,
            "FEE AMOUNT INCREASED",
        )
        self.assertEqual(analysis.purchases, ())
        self.assertEqual(analysis.standalone_fees, ())

    def test_duplicate_candidates_are_not_reclassified_as_large_purchases(self) -> None:
        rows = (
            transaction(1, amount=1_000),
            transaction(2, amount=1_000),
            transaction(3, amount=100, merchant="other", day=11),
        )
        analysis = analyze_monthly_observations(MonthlyObservationDataset(
            MONTH, (MONTH,), rows,
        ))
        self.assertEqual(analysis.duplicate_transaction_ids, frozenset({1, 2}))
        self.assertEqual(analysis.purchases, ())

    def test_merchant_activity_suppresses_unusual_but_keeps_large_purchase(self) -> None:
        rows = []
        transaction_id = 1
        for month in ("2030-01", "2030-02", "2030-03"):
            for day in (2, 8, 14):
                rows.append(transaction(
                    transaction_id, month=month, day=day, amount=100,
                ))
                transaction_id += 1
        rows.extend(
            transaction(transaction_id + offset, day=20 + offset, amount=600)
            for offset in range(6)
        )
        analysis = analyze_monthly_observations(MonthlyObservationDataset(
            MONTH,
            ("2030-01", "2030-02", "2030-03", MONTH),
            tuple(rows),
        ))
        self.assertEqual(len(analysis.merchant_activity), 1)
        self.assertTrue(analysis.purchases)
        self.assertTrue(all(
            finding.signal.observation_type == "LARGE PURCHASE"
            for finding in analysis.purchases
        ))

    def test_standalone_fee_excludes_reviewed_recurring_transaction(self) -> None:
        rows = (
            transaction(1, merchant="reviewed fee", notes="fee"),
            transaction(2, merchant="other fee", notes="fee", day=11),
        )
        series = MonthlyRecurringSeries(
            "series-1", "Reviewed fee", "Synthetic category",
            "Fixed recurring", "Monthly", ("reviewed fee",),
        )
        analysis = analyze_monthly_observations(MonthlyObservationDataset(
            MONTH, (MONTH,), rows, (series,),
        ))
        self.assertEqual(
            tuple(finding.signal.transaction_id for finding in analysis.standalone_fees),
            (2,),
        )


if __name__ == "__main__":
    unittest.main()
