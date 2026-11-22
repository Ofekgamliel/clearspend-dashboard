"""Read-only input assembly for backend financial-observation analysis."""

from __future__ import annotations

from dataclasses import dataclass, field

from clearspend.database.connection import DatabaseTarget, database_connection
from clearspend.database.postgresql import PostgreSQLPool
from clearspend.observations.snapshot_queries import (
    observation_household_history,
    observation_installments_by_month,
    observation_recurring_by_month,
    observation_review_keys,
    observation_scope_inputs,
    observation_transaction_history,
)
from clearspend.observations.scope import ObservationScope, build_observation_scope


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
    installments_by_month: dict[str, dict] = field(default_factory=dict)


def load_observation_inputs(
    database: DatabaseTarget,
    *,
    period: str,
    card: str,
    month: str = "",
    income_hidden: bool = False,
) -> ObservationInputSnapshot:
    """Load one consistent, bounded database snapshot for observation analysis."""
    with database_connection(database) as connection:
        try:
            if isinstance(database, PostgreSQLPool):
                connection.execute(
                    "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"
                )
            else:
                connection.execute("BEGIN")
            available_months, start, end, label = observation_scope_inputs(
                connection,
                period,
                month,
            )
            scope = build_observation_scope(
                period=period,
                available_months=available_months,
                selected_month=month,
                period_start=start or "",
                period_end=end or "",
            )
            history_rows = observation_transaction_history(
                connection,
                card,
                scope.scope_end,
            )
            grouped_transactions: dict[str, list[dict]] = {
                current: [] for current in scope.history_months
            }
            for row in history_rows:
                report_month = str(
                    row.get("billing_month")
                    or str(row.get("billing_date") or "")[:7]
                    or str(row.get("transaction_date") or "")[:7]
                )
                if report_month in grouped_transactions:
                    grouped_transactions[report_month].append(row)
            transactions_by_month = {
                current: tuple(rows) for current, rows in grouped_transactions.items()
            }
            recurring_by_month = observation_recurring_by_month(
                connection,
                scope.recurring_months,
                card,
            )
            if card == "all":
                household_history, partial_month = observation_household_history(
                    connection
                )
            else:
                household_history, partial_month = {}, ""
            reviewed_finding_keys = observation_review_keys(connection)
            installments_by_month = observation_installments_by_month(
                connection,
                scope.history_months,
                card,
            )
        finally:
            connection.rollback()
    dashboard = {
        "period": {"key": period, "start": start, "end": end, "label": label},
        "available_months": list(reversed(available_months)),
    }
    return ObservationInputSnapshot(
        scope=scope,
        selected_card=card,
        income_visible=card == "all" and not income_hidden,
        partial_month=partial_month,
        dashboard=dashboard,
        transactions_by_month=transactions_by_month,
        recurring_by_month=recurring_by_month,
        household_history=household_history,
        reviewed_finding_keys=reviewed_finding_keys,
        installments_by_month=installments_by_month,
    )
