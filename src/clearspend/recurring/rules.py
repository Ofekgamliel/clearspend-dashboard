from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from clearspend.reporting.periods import month_number, shift_month


ALLOWED_RECURRING_TYPES = frozenset({
    "Fixed recurring",
    "Usage-based recurring",
    "Scheduled obligation",
    "Other recurring",
})
CADENCE_MONTHS = {
    "Weekly": 0,
    "Monthly": 1,
    "Every 2 months": 2,
    "Quarterly": 3,
    "Every 6 months": 6,
    "Yearly": 12,
    "Custom": 0,
    "Irregular": 0,
    "Unknown": 0,
}
LIFECYCLE_STATUSES = frozenset({"active", "ended", "paused", "unknown"})


@dataclass(frozen=True)
class RecurringSeriesAssessment:
    amount: float | None
    amount_kind: str
    coverage: str
    status: str
    last_billed_month: str
    scoped_months: tuple[str, ...]
    typical_amount: float
    history: tuple[dict, ...]


def median(values: list[float]) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    middle = len(ordered) // 2
    return (
        ordered[middle]
        if len(ordered) % 2
        else (ordered[middle - 1] + ordered[middle]) / 2
    )


def month_history(
    amounts: Mapping[str, float],
    end_month: str,
    cadence_months: int,
    lifecycle_status: str = "active",
    end_profile_month: str | None = None,
) -> list[dict]:
    if not amounts:
        return []
    first_month = min(amounts)
    start_number = max(month_number(first_month), month_number(end_month) - 11)
    history: list[dict] = []
    for number in range(start_number, month_number(end_month) + 1):
        current = f"{number // 12:04d}-{number % 12 + 1:02d}"
        amount = round(amounts.get(current, 0.0), 2)
        after_end = (
            lifecycle_status == "ended"
            and bool(end_profile_month)
            and current > end_profile_month
        )
        expected = (
            cadence_months > 0
            and not after_end
            and lifecycle_status == "active"
            and (number - month_number(first_month)) % cadence_months == 0
        )
        if expected and cadence_months >= 6:
            expected = not any(
                amounts.get(shift_month(current, offset), 0) for offset in (-1, 1)
            )
        history.append({
            "month": current,
            "amount": amount if amount else None,
            "state": "charged" if amount else "missing" if expected else "not_expected",
        })
    return history


def assess_recurring_series(
    amounts: Mapping[str, float],
    *,
    period: str,
    start_month: str,
    end_month: str,
    cadence_months: int,
    lifecycle_status: str,
    end_profile_month: str | None,
    recurring_type: str,
) -> RecurringSeriesAssessment | None:
    if not amounts:
        return None
    recorded_months = sorted(amounts)
    last_month = recorded_months[-1]
    actual = amounts.get(start_month) if period == "month" else None

    annual_state = None
    due_month = None
    if period == "month" and cadence_months == 12:
        if actual is not None:
            annual_state = "paid"
            due_month = start_month
        else:
            due_month = shift_month(last_month, 12)
            distance = month_number(start_month) - month_number(due_month)
            annual_state = (
                "upcoming" if distance == -1
                else "due" if distance == 0
                else "overdue" if distance > 0
                else None
            )
            if annual_state is None:
                return None

    if period == "month":
        if last_month > end_month or (
            lifecycle_status == "ended"
            and end_profile_month
            and start_month > end_profile_month
        ):
            return None
    elif not any(start_month <= month <= end_month for month in recorded_months):
        return None

    scoped_months = tuple(
        month for month in recorded_months if start_month <= month <= end_month
    )
    scoped_amount = round(sum(amounts[month] for month in scoped_months), 2)
    previous_amounts = [amounts[month] for month in recorded_months[:-1]]
    typical = median(list(amounts.values()))
    increased = bool(previous_amounts and amounts[last_month] > previous_amounts[-1] * 1.15)
    overdue = (
        cadence_months > 0
        and month_number(end_month) - month_number(last_month)
        > max(cadence_months + 1, 2)
    )

    if lifecycle_status != "active":
        status = lifecycle_status
    elif annual_state:
        status = annual_state
    elif actual is None and period == "month":
        status = "missing" if overdue else "expected"
    elif increased:
        status = "increased"
    elif recurring_type == "Usage-based recurring":
        status = "variable"
    else:
        status = "confirmed"

    if annual_state == "paid":
        coverage = f"Paid {start_month}; next {shift_month(start_month, 12)}"
    elif annual_state:
        coverage = f"{annual_state.title()} {due_month}"
    elif recurring_type == "Usage-based recurring":
        recent = [amounts[month] for month in recorded_months[-6:]]
        coverage = f"Recent range {min(recent):.2f}–{max(recent):.2f}"
    else:
        coverage = (
            f"Expected {shift_month(last_month, cadence_months)}"
            if cadence_months else "No reliable schedule"
        )

    if period == "month":
        amount = actual
        amount_kind = "billed"
    elif period == "year":
        amount = scoped_amount / max(len(scoped_months), 1)
        amount_kind = "monthly_average"
    else:
        amount = scoped_amount
        amount_kind = "period_total"

    return RecurringSeriesAssessment(
        amount=round(amount, 2) if amount is not None else None,
        amount_kind=amount_kind,
        coverage=coverage,
        status=status,
        last_billed_month=last_month,
        scoped_months=scoped_months,
        typical_amount=round(typical, 2),
        history=tuple(month_history(
            amounts,
            end_month,
            cadence_months,
            lifecycle_status,
            end_profile_month,
        )),
    )
