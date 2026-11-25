"""Public orchestration and response assembly for three-month forecasts."""

from __future__ import annotations

from decimal import Decimal
from typing import Iterable

from clearspend.recurring.forecast_common import money
from clearspend.recurring.forecast_models import (
    ChargeEvidence,
    InstallmentForecastEvidence,
    InternalOccurrence,
    RecurringForecastEvidence,
    UnresolvedForecast,
)
from clearspend.recurring.installment_forecast import installment_occurrences
from clearspend.recurring.recurring_forecast import recurring_occurrences
from clearspend.reporting.periods import shift_month


def _public_occurrence(item: InternalOccurrence) -> dict:
    """Map the typed internal occurrence to the intentionally small API row."""
    return {
        "occurrence_id": item["occurrence_id"],
        "expected_date": item["expected_date"],
        "date_evidence": item["date_evidence"],
        "display_name": item["display_name"],
        "card": item["card"],
        "payment_type": item["payment_type"],
        "amount": item["amount"],
        "amount_evidence": item["amount_evidence"],
        "amount_confidence": item["amount_confidence"],
        "occurrence_status": item["occurrence_status"],
        "recent_range": item["recent_range"],
        "installment_number": item["installment_number"],
        "installment_total": item["installment_total"],
        "annual": item["annual"],
        "ending": item["ending"],
    }


def _public_unresolved(item: UnresolvedForecast) -> dict:
    return {
        "source_kind": item["source_kind"],
        "source_id": item["source_id"],
        "display_name": item["display_name"],
        "card": item["card"],
        "reason": item["reason"],
    }


def build_upcoming_forecast(
    recurring_profiles: Iterable[RecurringForecastEvidence],
    installment_plans: Iterable[InstallmentForecastEvidence],
    *,
    anchor_month: str,
    generated_as_of: str,
    selected_card: str = "all",
) -> dict:
    """Build a deterministic informational forecast from bounded evidence."""
    horizon_end = shift_month(anchor_month, 2)
    occurrences: list[InternalOccurrence] = []
    unresolved: list[UnresolvedForecast] = []
    for profile in recurring_profiles:
        rows, issues = recurring_occurrences(profile, anchor_month, horizon_end)
        occurrences.extend(rows)
        unresolved.extend(issues)
    for plan in installment_plans:
        rows, issues = installment_occurrences(plan, anchor_month, horizon_end)
        occurrences.extend(rows)
        unresolved.extend(issues)

    if selected_card != "all":
        occurrences = [
            item for item in occurrences
            if f"{item['card']['provider']}:{item['card']['last4']}" == selected_card
        ]
        unresolved = [
            item for item in unresolved
            if item["card"] is not None
            and f"{item['card']['provider']}:{item['card']['last4']}" == selected_card
        ]

    month_rows: list[dict] = []
    for offset in range(3):
        month = shift_month(anchor_month, offset)
        payments = sorted(
            (item for item in occurrences if item["_month"] == month),
            key=lambda item: (
                item["expected_date"] or f"{month}-99",
                item["display_name"].casefold(),
                item["occurrence_id"],
            ),
        )
        confirmed = sum((
            Decimal(str(item["amount"])) for item in payments
            if item["amount"] is not None and item["amount_evidence"] == "confirmed"
        ), Decimal(0))
        forecast = sum((
            Decimal(str(item["amount"])) for item in payments
            if item["amount"] is not None and item["amount_evidence"] != "confirmed"
        ), Decimal(0))
        month_rows.append({
            "month": month,
            "confirmed_total": money(confirmed),
            "forecast_total": money(forecast),
            "comparable_total": money(confirmed + forecast),
            "unknown_amount_count": sum(item["amount"] is None for item in payments),
            "payment_count": len(payments),
            "comparison_label": None,
            "annual_count": sum(bool(item["annual"]) for item in payments),
            "ending_installment_count": sum(bool(item["ending"]) for item in payments),
            "payments": [_public_occurrence(item) for item in payments],
        })

    totals = [item["comparable_total"] for item in month_rows]
    largest = max(totals)
    if totals.count(largest) == 1:
        index = totals.index(largest)
        complete = (
            not unresolved
            and all(item["unknown_amount_count"] == 0 for item in month_rows)
        )
        month_rows[index]["comparison_label"] = (
            "highest_expected" if complete else "highest_known_estimate"
        )
    return {
        "generated_as_of": generated_as_of,
        "anchor_month": anchor_month,
        "horizon_start": anchor_month,
        "horizon_end": horizon_end,
        "selected_card": selected_card,
        "months": month_rows,
        "unresolved": [
            _public_unresolved(item) for item in sorted(
                unresolved,
                key=lambda item: (item["display_name"].casefold(), item["reason"]),
            )
        ],
    }
