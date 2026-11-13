from __future__ import annotations

import unittest

from clearspend.reporting.purchase_activity import PurchaseActivityRow, build_purchase_activity


def row(**changes) -> PurchaseActivityRow:
    values = {
        "transaction_date": "2030-01-10",
        "category": "Synthetic category",
        "personal_amount": 100.0,
        "provider": "synthetic",
        "card_last4": "0001",
        "merchant_normalized": "synthetic merchant",
        "charged_amount": "100.00",
        "original_amount": None,
        "original_currency": "ILS",
        "charged_currency": "ILS",
        "installment_number": None,
        "installment_total": None,
    }
    values.update(changes)
    return PurchaseActivityRow(**values)


class PurchaseActivityTests(unittest.TestCase):
    def test_regular_purchases_use_personal_amount_and_group_by_category(self) -> None:
        trend, summary = build_purchase_activity(
            [row(personal_amount=25), row(personal_amount=75)],
            billed_charges=200,
            billed_refunds=10,
        )

        self.assertEqual(trend[0]["amount"], 100)
        self.assertEqual(trend[0]["categories"], [
            {"category": "Synthetic category", "amount": 100.0}
        ])
        self.assertEqual(summary["purchases"], 2)
        self.assertEqual(summary["billed_charges"], 200)
        self.assertEqual(summary["billed_refunds"], 10)

    def test_installments_collapse_to_original_same_currency_purchase(self) -> None:
        trend, summary = build_purchase_activity(
            [
                row(installment_number=1, installment_total=3, original_amount="300.00"),
                row(installment_number=2, installment_total=3, original_amount="300.00"),
            ],
            billed_charges=200,
            billed_refunds=0,
        )

        self.assertEqual(trend[0]["amount"], 300)
        self.assertEqual(summary["purchases"], 1)
        self.assertEqual(summary["installment_plans"], 1)

    def test_installment_currency_mismatch_estimates_full_plan_from_average(self) -> None:
        trend, _summary = build_purchase_activity(
            [
                row(
                    charged_amount="33.33",
                    installment_number=1,
                    installment_total=3,
                    original_amount="25.00",
                    original_currency="USD",
                ),
                row(
                    charged_amount="33.34",
                    installment_number=2,
                    installment_total=3,
                    original_amount="25.00",
                    original_currency="USD",
                ),
            ],
            billed_charges=66.67,
            billed_refunds=0,
        )

        self.assertEqual(trend[0]["amount"], 100.01)

    def test_first_installment_category_controls_plan_category(self) -> None:
        trend, _summary = build_purchase_activity(
            [
                row(category="First category", installment_number=1, installment_total=2),
                row(category="Changed category", installment_number=2, installment_total=2),
            ],
            billed_charges=200,
            billed_refunds=0,
        )

        self.assertEqual(trend[0]["categories"][0]["category"], "First category")


if __name__ == "__main__":
    unittest.main()
