"""Adapt read-only observation snapshots to long-period rule inputs."""

from __future__ import annotations

from clearspend.observations.historical_analysis import (
    HistoricalObservationAnalysis,
    HistoricalObservationDataset,
    analyze_historical_observations,
)
from clearspend.observations.historical_merchant_rules import (
    HistoricalMerchantTransaction,
)
from clearspend.observations.historical_rules import (
    HistoricalCategoryTransaction,
    HistoricalHouseholdMonth,
    HistoricalInstallmentMonth,
    HistoricalInstallmentPlan,
    HistoricalRecurringMonth,
    HistoricalRecurringSeries,
    HistoricalTransaction,
)
from clearspend.observations.inputs import ObservationInputSnapshot


def _number(value: object) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


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


def _transaction_inputs(
    snapshot: ObservationInputSnapshot,
) -> tuple[
    tuple[HistoricalTransaction, ...],
    tuple[HistoricalCategoryTransaction, ...],
    tuple[HistoricalMerchantTransaction, ...],
]:
    routine: list[HistoricalTransaction] = []
    categories: list[HistoricalCategoryTransaction] = []
    merchants: list[HistoricalMerchantTransaction] = []
    for report_month in snapshot.scope.history_months:
        for row in snapshot.transactions_by_month.get(report_month, ()):
            amount = _number(row.get("personal_amount"))
            event_id = _event_id(row.get("event_id"))
            category = str(row.get("category") or "Needs review")
            merchant_label = str(
                row.get("merchant_display_name") or row.get("merchant_raw") or ""
            )
            routine.append(HistoricalTransaction(
                month=report_month,
                personal_amount=amount,
                event_id=event_id,
            ))
            categories.append(HistoricalCategoryTransaction(
                month=report_month,
                category=category,
                merchant_label=merchant_label,
                personal_amount=amount,
                event_id=event_id,
            ))
            merchants.append(HistoricalMerchantTransaction(
                identity="\0".join((
                    str(
                        row.get("canonical_merchant_id")
                        or row.get("merchant_normalized")
                        or row.get("merchant_raw")
                        or ""
                    ),
                    category,
                )),
                merchant_label=merchant_label,
                merchant_raw=str(row.get("merchant_raw") or ""),
                transaction_date=str(row.get("transaction_date") or ""),
                personal_amount=amount,
                category=category,
                installment_total=_integer(row.get("installment_total")),
                event_id=event_id,
            ))
    return tuple(routine), tuple(categories), tuple(merchants)


def _household_inputs(
    snapshot: ObservationInputSnapshot,
) -> dict[str, HistoricalHouseholdMonth]:
    return {
        month: HistoricalHouseholdMonth(
            month=month,
            income=_number(row.get("income")),
            spending=_number(row.get("amount")),
        )
        for month, row in snapshot.household_history.items()
    }


def _recurring_inputs(
    snapshot: ObservationInputSnapshot,
) -> tuple[
    dict[str, HistoricalRecurringMonth],
    dict[str, HistoricalInstallmentMonth],
    tuple[str, ...],
]:
    recurring_history: dict[str, HistoricalRecurringMonth] = {}
    installment_history: dict[str, HistoricalInstallmentMonth] = {}
    aliases: set[str] = set()
    for month in snapshot.scope.recurring_months:
        payload = snapshot.recurring_by_month.get(month) or {}
        series: list[HistoricalRecurringSeries] = []
        for row in payload.get("series") or ():
            source_aliases = tuple(
                str(value) for value in (row.get("source_aliases") or ()) if value
            )
            aliases.update(source_aliases)
            series.append(HistoricalRecurringSeries(
                series_id=str(row.get("series_id") or ""),
                amount=_number(row.get("amount")),
                cadence=str(row.get("cadence") or "Unknown"),
                status=str(row.get("lifecycle_status") or row.get("status") or ""),
                display_name=str(row.get("display_name") or ""),
                source_aliases=source_aliases,
            ))
        metrics = payload.get("metrics") or {}
        recurring_history[month] = HistoricalRecurringMonth(
            month=month,
            series=tuple(series),
            active_series_count=_integer(metrics.get("active_series")),
        )

        dedicated_installments = snapshot.installments_by_month.get(month) or {}
        commitment_rows = dedicated_installments.get("plans")
        if commitment_rows is None:
            commitment_rows = payload.get("commitments") or ()
        commitments = tuple(
            HistoricalInstallmentPlan(
                plan_id=str(row.get("plan_id") or "") or None,
                source_alias=str(row.get("source_alias") or ""),
                display_name=str(row.get("display_name") or ""),
                original_purchase_date=str(row.get("original_purchase_date") or ""),
                original_amount=row.get("original_amount") or "",
                installment_total=(
                    row.get("installment_total")
                    or row.get("total_installments")
                    or ""
                ),
            )
            for row in commitment_rows
        )
        installment_history[month] = HistoricalInstallmentMonth(
            month=month,
            installment_billed=_number(
                dedicated_installments.get(
                    "installment_billed",
                    metrics.get("installment_billed"),
                ),
            ),
            commitments=commitments,
        )
    return recurring_history, installment_history, tuple(sorted(aliases))


def historical_dataset_from_snapshot(
    snapshot: ObservationInputSnapshot,
) -> HistoricalObservationDataset:
    """Normalize an existing long-period snapshot without new database reads."""
    if not snapshot.scope.historical:
        raise ValueError("Historical observation analysis requires a long period")
    routine, categories, merchants = _transaction_inputs(snapshot)
    recurring, installments, aliases = _recurring_inputs(snapshot)
    return HistoricalObservationDataset(
        target_months=snapshot.scope.target_months,
        coverage_months=snapshot.scope.history_months,
        routine_transactions=routine,
        category_transactions=categories,
        merchant_transactions=merchants,
        household_history=_household_inputs(snapshot),
        recurring_history=recurring,
        installment_history=installments,
        recurring_aliases=aliases,
        partial_month=snapshot.partial_month,
        income_visible=snapshot.income_visible,
    )


def analyze_historical_snapshot(
    snapshot: ObservationInputSnapshot,
) -> HistoricalObservationAnalysis:
    """Adapt and analyze one snapshot through the pure coordinator boundary."""
    return analyze_historical_observations(historical_dataset_from_snapshot(snapshot))
