"""Adapt read-only observation snapshots to single-month rule inputs."""

from __future__ import annotations

from clearspend.observations.inputs import ObservationInputSnapshot
from clearspend.observations.monthly_analysis import (
    MonthlyObservationAnalysis,
    MonthlyObservationDataset,
    MonthlyObservationTransaction,
    MonthlyRecurringSeries,
    analyze_monthly_observations,
)
from clearspend.observations.monthly_rules import HouseholdMonth


def _number(value: object) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _optional_number(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _integer(value: object) -> int | None:
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _event_id(value: object) -> int | str | None:
    """Preserve numeric IDs and the event slugs exposed by transaction reads."""
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return str(value)


def _transactions(
    snapshot: ObservationInputSnapshot,
) -> tuple[MonthlyObservationTransaction, ...]:
    transactions: list[MonthlyObservationTransaction] = []
    for report_month in snapshot.scope.history_months:
        for row in snapshot.transactions_by_month.get(report_month, ()):
            transaction_id = _integer(row.get("id"))
            if transaction_id is None:
                continue
            transaction_date = str(
                row.get("transaction_date")
                or row.get("billing_date")
                or f"{report_month}-01"
            )
            transactions.append(MonthlyObservationTransaction(
                id=transaction_id,
                report_month=report_month,
                merchant_raw=str(row.get("merchant_raw") or ""),
                merchant_normalized=str(row.get("merchant_normalized") or ""),
                merchant_display_name=str(
                    row.get("merchant_display_name") or ""
                ),
                canonical_merchant_id=str(
                    row.get("canonical_merchant_id") or ""
                ),
                category=str(row.get("category") or "Needs review"),
                provider=str(row.get("provider") or ""),
                card_last4=str(row.get("card_last4") or ""),
                transaction_date=transaction_date,
                charged_amount=_number(
                    row.get("amount")
                    if row.get("amount") is not None
                    else row.get("charged_amount")
                ),
                charged_currency=str(row.get("charged_currency") or ""),
                personal_amount=_number(
                    row.get("personal_amount")
                    if row.get("personal_amount") is not None
                    else row.get("amount")
                ),
                installment_total=_integer(row.get("installment_total")),
                original_amount=_optional_number(row.get("original_amount")),
                original_currency=(
                    str(row.get("original_currency"))
                    if row.get("original_currency") not in (None, "")
                    else None
                ),
                notes=str(row.get("notes") or ""),
                event_id=_event_id(row.get("event_id")),
                event_name=str(row.get("event_name") or ""),
            ))
    return tuple(transactions)


def _recurring_series(
    snapshot: ObservationInputSnapshot,
    month: str,
) -> tuple[MonthlyRecurringSeries, ...]:
    payload = snapshot.recurring_by_month.get(month) or {}
    return tuple(
        MonthlyRecurringSeries(
            series_id=str(row.get("series_id") or ""),
            display_name=str(row.get("display_name") or ""),
            category=str(row.get("category") or "Needs review"),
            recurring_type=str(row.get("recurring_type") or "Other recurring"),
            cadence=str(row.get("cadence") or "Unknown"),
            source_aliases=tuple(
                str(alias)
                for alias in (row.get("source_aliases") or ())
                if alias
            ),
        )
        for row in (payload.get("series") or ())
    )


def _household_history(
    snapshot: ObservationInputSnapshot,
) -> dict[str, HouseholdMonth]:
    return {
        month: HouseholdMonth(
            month=month,
            income=_number(row.get("income")),
            spending=_number(row.get("amount")),
        )
        for month, row in snapshot.household_history.items()
    }


def monthly_dataset_from_snapshot(
    snapshot: ObservationInputSnapshot,
) -> MonthlyObservationDataset:
    """Normalize one existing monthly snapshot without another database read."""
    if snapshot.scope.historical:
        raise ValueError("Monthly observation analysis requires a month period")
    if not snapshot.scope.target_months:
        raise ValueError("Monthly observation analysis requires a selected month")
    month = snapshot.scope.target_months[0]
    return MonthlyObservationDataset(
        month=month,
        coverage_months=snapshot.scope.history_months,
        transactions=_transactions(snapshot),
        recurring_series=_recurring_series(snapshot, month),
        household_history=_household_history(snapshot),
        partial_month=snapshot.partial_month,
        income_visible=snapshot.income_visible,
    )


def analyze_monthly_snapshot(
    snapshot: ObservationInputSnapshot,
) -> MonthlyObservationAnalysis:
    """Adapt and analyze one snapshot through the pure monthly coordinator."""
    return analyze_monthly_observations(monthly_dataset_from_snapshot(snapshot))
