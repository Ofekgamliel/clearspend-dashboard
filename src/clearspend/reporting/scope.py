"""Pure construction of reporting-period, card, and event-scope filters."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReportingFilter:
    """SQL predicate and bound values for one reporting selection."""

    where: str
    parameters: tuple[object, ...]


def build_reporting_filter(
    reporting_month_sql: str,
    *,
    start: str | None,
    end: str | None,
    card: str,
    event_scope: str = "all",
) -> ReportingFilter:
    """Build the legacy-compatible transaction filter without database access."""

    if event_scope not in {"all", "routine"}:
        raise ValueError("Invalid event scope")

    conditions = [f"{reporting_month_sql} BETWEEN ? AND ?"]
    parameters: list[object] = [(start or "0000-00")[:7], (end or "9999-99")[:7]]

    # Preserve the existing behavior for malformed selections: only a
    # provider:last4 value narrows the result set.
    if card != "all" and ":" in card:
        provider, last4 = card.split(":", 1)
        conditions.extend(["provider = ?", "card_last4 = ?"])
        parameters.extend([provider, last4])

    if event_scope == "routine":
        conditions.append(
            "NOT EXISTS (SELECT 1 FROM event_transactions scoped_event "
            "WHERE scoped_event.transaction_id=t.id)"
        )

    return ReportingFilter(" AND ".join(conditions), tuple(parameters))
