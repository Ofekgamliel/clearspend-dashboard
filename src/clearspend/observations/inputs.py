"""Read-only input assembly for backend financial-observation analysis."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from clearspend.observations.queries import observation_reviews_payload
from clearspend.observations.scope import ObservationScope, build_observation_scope
from clearspend.recurring.queries import recurring_payload
from clearspend.reporting.dashboard import dashboard_payload
from clearspend.transactions.queries import transactions_payload


@dataclass(frozen=True)
class ObservationInputSnapshot:
    scope: ObservationScope
    selected_card: str
    income_visible: bool
    partial_month: str
    dashboard: dict
    transactions_by_month: dict[str, tuple[dict, ...]]
    recurring_by_month: dict[str, dict]
    household_history: dict[str, dict]
    reviewed_finding_keys: frozenset[str]


def load_observation_inputs(
    database: Path,
    *,
    period: str,
    card: str,
    month: str = "",
    income_hidden: bool = False,
) -> ObservationInputSnapshot:
    """Compose the same source payloads currently used by the browser engine."""
    dashboard = dashboard_payload(database, period, card, month)
    period_data = dashboard.get("period") or {}
    scope = build_observation_scope(
        period=period,
        available_months=dashboard.get("available_months") or (),
        selected_month=month,
        period_start=period_data.get("start") or "",
        period_end=period_data.get("end") or "",
    )
    transactions_by_month = {
        current: tuple(transactions_payload(
            database, "month", card, month=current,
        ).get("transactions") or ())
        for current in scope.history_months
    }
    recurring_by_month = {
        current: recurring_payload(database, "month", card, current)
        for current in scope.recurring_months
    }
    household_dashboard = (
        dashboard_payload(database, "all", "all") if card == "all" else None
    )
    household_history = {
        str(row.get("bucket")): row
        for row in (household_dashboard or {}).get("trend", ())
        if row.get("bucket")
    }
    average_data = (
        (household_dashboard or {}).get("income_summary", {}).get("averages", {})
    )
    partial_month = (
        str((dashboard.get("available_months") or [""])[0])
        if average_data.get("current_month_partial") else ""
    )
    reviews = observation_reviews_payload(database).get("reviews") or ()
    return ObservationInputSnapshot(
        scope=scope,
        selected_card=card,
        income_visible=card == "all" and not income_hidden,
        partial_month=partial_month,
        dashboard=dashboard,
        transactions_by_month=transactions_by_month,
        recurring_by_month=recurring_by_month,
        household_history=household_history,
        reviewed_finding_keys=frozenset(
            str(review.get("finding_key"))
            for review in reviews
            if review.get("finding_key")
        ),
    )
