"""Framework-independent event validation and transaction summaries."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Mapping


EVENT_TYPES = frozenset({"trip", "business_trip", "celebration", "home", "other"})
CREATE_STATUSES = frozenset({"planned", "active", "completed"})
EDIT_STATUSES = CREATE_STATUSES | {"cancelled"}


@dataclass(frozen=True)
class EventSettings:
    name: str
    event_type: str
    destination: str
    start: date
    end: date
    budget: float | None
    status: str


@dataclass(frozen=True)
class EventTransactionSummary:
    transaction_count: int
    amount: float
    total_transaction_count: int
    total_amount: float
    category_count: int
    card_count: int


def validate_event_settings(
    *,
    name: str,
    event_type: str,
    start_date: str,
    end_date: str,
    budget: object,
    status: str,
    destination: str = "",
    allow_cancelled: bool = False,
) -> EventSettings:
    """Normalize and validate settings shared by event creation and editing."""

    normalized_name = name.strip()
    normalized_type = event_type.strip()
    normalized_destination = destination.strip()
    normalized_status = status.strip()

    if not normalized_name:
        raise ValueError("Event name is required")
    if normalized_type not in EVENT_TYPES:
        raise ValueError("Invalid event type")
    if normalized_type == "business_trip" and not normalized_destination:
        raise ValueError("Destination is required for a business trip")
    if normalized_type != "business_trip":
        normalized_destination = ""

    allowed_statuses = EDIT_STATUSES if allow_cancelled else CREATE_STATUSES
    if normalized_status not in allowed_statuses:
        raise ValueError("Invalid event status")

    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
    except ValueError as error:
        raise ValueError("Valid start and end dates are required") from error
    if end < start:
        raise ValueError("End date cannot be before start date")

    budget_value = None
    if budget is not None and budget != "":
        try:
            budget_value = round(float(budget), 2)
        except (TypeError, ValueError) as error:
            raise ValueError("Budget must be a number") from error
        if budget_value < 0:
            raise ValueError("Budget cannot be negative")

    return EventSettings(
        name=normalized_name,
        event_type=normalized_type,
        destination=normalized_destination,
        start=start,
        end=end,
        budget=budget_value,
        status=normalized_status,
    )


def summarize_event_transactions(
    transactions: list[Mapping[str, object]],
    *,
    period_start: str,
    period_end: str,
) -> EventTransactionSummary:
    """Calculate selected-period and lifetime totals for one event."""

    scoped = [
        row
        for row in transactions
        if period_start <= str(row.get("transaction_date") or "") <= period_end
    ]

    def personal_total(rows: list[Mapping[str, object]]) -> float:
        return round(sum(float(row.get("personal_amount") or 0) for row in rows), 2)

    return EventTransactionSummary(
        transaction_count=len(scoped),
        amount=personal_total(scoped),
        total_transaction_count=len(transactions),
        total_amount=personal_total(transactions),
        category_count=len({row.get("category") for row in transactions}),
        card_count=len({(row.get("provider"), row.get("card_last4")) for row in transactions}),
    )
