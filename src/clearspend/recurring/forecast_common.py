"""Shared bounded forecast calculations and occurrence construction."""

from __future__ import annotations

import calendar
from datetime import date
from decimal import Decimal
from typing import Sequence

from clearspend.recurring.forecast_models import ChargeEvidence, InternalOccurrence


def money(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.01")))


def median(values: Sequence[Decimal]) -> Decimal:
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / Decimal(2)


def card_dict(card: str) -> dict[str, str]:
    provider, last4 = card.split(":", 1)
    return {"provider": provider, "last4": last4}


def date_day(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10]).day
    except ValueError:
        return None


def confirmed_date(charge: ChargeEvidence) -> str | None:
    """Return exact billing evidence without inventing a day from a month."""
    if charge.billing_date:
        try:
            return date.fromisoformat(charge.billing_date[:10]).isoformat()
        except ValueError:
            return None
    if charge.transaction_date and charge.transaction_date[:7] == charge.report_month:
        try:
            return date.fromisoformat(charge.transaction_date[:10]).isoformat()
        except ValueError:
            return None
    return None


def is_ils(value: str | None) -> bool:
    return (value or "").strip().upper() in {"ILS", "₪"}


def estimated_date(
    charges: Sequence[ChargeEvidence], target_month: str,
) -> str | None:
    recent = sorted(
        charges, key=lambda item: (item.report_month, item.transaction_key),
    )[-4:]
    days = [
        day for item in recent
        if (day := date_day(confirmed_date(item))) is not None
    ]
    if len(days) < 3:
        return None
    median_day = int(median([Decimal(day) for day in days]))
    if any(abs(day - median_day) > 3 for day in days):
        return None
    year, month = (int(part) for part in target_month.split("-"))
    day = min(median_day, calendar.monthrange(year, month)[1])
    return f"{target_month}-{day:02d}"


def actual_occurrence(
    charge: ChargeEvidence, *, occurrence_id: str, display_name: str,
    payment_type: str, status: str, annual: bool = False, ending: bool = False,
) -> InternalOccurrence:
    exact_date = confirmed_date(charge)
    amount_known = is_ils(charge.charged_currency)
    return {
        "occurrence_id": occurrence_id,
        "expected_date": exact_date,
        "date_evidence": "confirmed" if exact_date else "month_only",
        "display_name": display_name,
        "card": card_dict(charge.card),
        "payment_type": payment_type,
        "amount": money(charge.amount) if amount_known else None,
        "amount_evidence": "confirmed" if amount_known else "unknown",
        "amount_confidence": None,
        "occurrence_status": status,
        "recent_range": None,
        "installment_number": charge.installment_number,
        "installment_total": charge.installment_total,
        "annual": annual,
        "ending": ending,
        "_month": charge.report_month,
        "_logical_card": charge.card,
    }


def single_evidence_card(charges: Sequence[ChargeEvidence]) -> str | None:
    cards = {item.card for item in charges}
    return next(iter(cards)) if len(cards) == 1 else None
