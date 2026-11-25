"""Stable recurring and installment identity helpers."""

from __future__ import annotations

import hashlib
from decimal import Decimal, InvalidOperation


def _amount_identity(value: object) -> str:
    if value in {None, ""}:
        return ""
    try:
        normalized = Decimal(str(value)).normalize()
    except InvalidOperation:
        return str(value).strip()
    return format(normalized, "f")


def installment_plan_identity(
    provider: object,
    card_last4: object,
    canonical_group_id: object,
    transaction_date: object,
    original_amount: object,
    installment_total: object,
) -> str:
    """Derive an opaque ID from the provider evidence that identifies one plan."""
    components = (
        str(provider or "").strip().lower(),
        str(card_last4 or "").strip(),
        str(canonical_group_id or "").strip().lower(),
        str(transaction_date or "").strip(),
        _amount_identity(original_amount),
        str(int(installment_total or 0)),
    )
    digest = hashlib.sha256("\x1f".join(components).encode("utf-8")).hexdigest()
    return f"commitment_{digest[:24]}"


def _opaque_identity(namespace: str, *components: object) -> str:
    normalized = "\x1f".join(str(value or "").strip() for value in components)
    digest = hashlib.sha256(f"{namespace}\x1e{normalized}".encode("utf-8")).hexdigest()
    return f"{namespace}_{digest[:24]}"


def recurring_series_identity(profile_id: str, logical_card_slot: str) -> str:
    return _opaque_identity("series", profile_id, logical_card_slot)


def recurring_occurrence_identity(
    recurring_series_id: str, report_month: str,
) -> str:
    return _opaque_identity("occurrence_recurring", recurring_series_id, report_month)


def installment_occurrence_identity(commitment_id: str, installment_number: int) -> str:
    return _opaque_identity("occurrence_installment", commitment_id, installment_number)


def unexpected_actual_identity(transaction_key: str) -> str:
    return _opaque_identity("occurrence_actual", transaction_key)
