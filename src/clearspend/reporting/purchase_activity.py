from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable


@dataclass(frozen=True)
class PurchaseActivityRow:
    transaction_date: str
    category: str
    personal_amount: float
    provider: str
    card_last4: str
    merchant_normalized: str
    charged_amount: str | None
    original_amount: str | None
    original_currency: str | None
    charged_currency: str | None
    installment_number: int | None
    installment_total: int | None


def _money(value: float) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def build_purchase_activity(
    rows: Iterable[PurchaseActivityRow],
    *,
    billed_charges: float,
    billed_refunds: float,
) -> tuple[list[dict], dict]:
    """Collapse installment rows into purchases and aggregate purchase-date activity."""
    regular: list[tuple[str, str, float, int]] = []
    plans: dict[tuple, list[PurchaseActivityRow]] = defaultdict(list)
    for row in rows:
        if row.installment_number is None:
            regular.append((row.transaction_date, row.category, row.personal_amount, 0))
            continue
        key = (
            row.provider,
            row.card_last4,
            row.merchant_normalized,
            row.transaction_date,
            row.original_amount,
            row.original_currency,
            row.charged_currency,
            row.installment_total,
        )
        plans[key].append(row)

    purchases = list(regular)
    for plan_rows in plans.values():
        first_categories = [
            row.category for row in plan_rows if row.installment_number == 1
        ]
        category = max(first_categories or [row.category for row in plan_rows])
        example = plan_rows[0]
        if (
            example.original_amount is not None
            and (example.original_currency or "") == (example.charged_currency or "")
        ):
            plan_amount = float(example.original_amount)
        else:
            charged = [float(row.charged_amount or 0) for row in plan_rows]
            total_installments = max(row.installment_total or 0 for row in plan_rows)
            plan_amount = _money(sum(charged) / len(charged) * total_installments)
        purchases.append((example.transaction_date, category, plan_amount, 1))

    category_totals: dict[tuple[str, str], dict[str, float | int]] = {}
    for transaction_date, category, purchase_amount, installment_plan in purchases:
        aggregate = category_totals.setdefault(
            (transaction_date, category),
            {"amount": 0.0, "purchases": 0, "installment_plans": 0},
        )
        aggregate["amount"] = float(aggregate["amount"]) + purchase_amount
        aggregate["purchases"] = int(aggregate["purchases"]) + 1
        aggregate["installment_plans"] = (
            int(aggregate["installment_plans"]) + installment_plan
        )

    grouped_rows = [
        {
            "bucket": transaction_date,
            "category": category,
            "amount": _money(float(values["amount"])),
            "purchases": int(values["purchases"]),
            "installment_plans": int(values["installment_plans"]),
        }
        for (transaction_date, category), values in category_totals.items()
    ]
    # Match SQLite's established grouped-row tie order: date and amount are
    # primary, with category descending when rounded amounts are equal.
    grouped_rows.sort(key=lambda row: row["category"], reverse=True)
    grouped_rows.sort(key=lambda row: (row["bucket"], -row["amount"]))

    activity_by_day: dict[str, dict] = {}
    for row in grouped_rows:
        day = activity_by_day.setdefault(
            row["bucket"], {"bucket": row["bucket"], "amount": 0.0, "categories": []}
        )
        day["amount"] += row["amount"]
        day["categories"].append({"category": row["category"], "amount": row["amount"]})
    trend = []
    for day in activity_by_day.values():
        day["amount"] = _money(day["amount"])
        trend.append(day)

    summary = {
        "total": _money(sum(row["amount"] for row in grouped_rows)) if grouped_rows else 0,
        "purchases": sum(row["purchases"] for row in grouped_rows),
        "active_days": len(activity_by_day),
        "installment_plans": sum(row["installment_plans"] for row in grouped_rows),
        "billed_charges": round(billed_charges, 2),
        "billed_refunds": round(billed_refunds, 2),
    }
    return trend, summary
