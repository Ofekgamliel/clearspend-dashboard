from __future__ import annotations

from pathlib import Path
from typing import Mapping, Sequence

from clearspend.events.queries import events_payload
from clearspend.events.service import create_event, save_event_settings, save_transaction_event
from clearspend.merchants.queries import mapping_payload, merchants_payload
from clearspend.merchants.service import save_mapping, save_merchant
from clearspend.observations.queries import observation_reviews_payload
from clearspend.observations.payloads import observations_payload
from clearspend.observations.service import save_observation_review
from clearspend.recurring.queries import recurring_payload
from clearspend.recurring.service import manage_recurring_profile, save_recurring_profile
from clearspend.reporting.category_queries import categories_payload
from clearspend.reporting.dashboard import dashboard_payload
from clearspend.transactions.queries import transactions_payload
from clearspend.transactions.service import save_transaction_adjustment, save_transaction_category


JSON_GET_PATHS = frozenset({
    "/api/health",
    "/api/dashboard",
    "/api/transactions",
    "/api/categories",
    "/api/mapping",
    "/api/merchants",
    "/api/recurring",
    "/api/events",
    "/api/observations",
    "/api/observation-reviews",
})

JSON_POST_PATHS = frozenset({
    "/api/mapping",
    "/api/merchants",
    "/api/transaction-category",
    "/api/transaction-adjustment",
    "/api/transaction-event",
    "/api/events",
    "/api/event-settings",
    "/api/observation-review",
    "/api/recurring-profile",
    "/api/recurring-profile/manage",
})


def _first(query: Mapping[str, Sequence[str]], key: str, default: str) -> str:
    values = query.get(key)
    return values[0] if values else default


def _boolean_query(
    query: Mapping[str, Sequence[str]], key: str, default: bool = False,
) -> bool:
    value = _first(query, key, "true" if default else "false").strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Invalid {key}")


def dispatch_json_get(
    database: Path,
    path: str,
    query: Mapping[str, Sequence[str]],
) -> tuple[dict, int]:
    """Dispatch a decoded GET request to a read/query service."""
    if path not in JSON_GET_PATHS:
        raise ValueError("Unknown JSON API route")
    if path == "/api/health":
        return {"status": "ok", "mode": "local", "database": database.exists()}, 200
    if path == "/api/mapping":
        return mapping_payload(database), 200
    if path == "/api/merchants":
        return merchants_payload(database), 200
    if path == "/api/observation-reviews":
        return observation_reviews_payload(database), 200
    period = _first(query, "period", "month")
    if period not in {"month", "year", "all"}:
        raise ValueError("Invalid period")
    card = _first(query, "card", "all")
    month = _first(query, "month", "")
    if path == "/api/dashboard":
        return dashboard_payload(database, period, card, month), 200
    if path in {"/api/transactions", "/api/categories"}:
        event_scope = _first(query, "event_scope", "all")
        if event_scope not in {"all", "routine"}:
            raise ValueError("Invalid event scope")
        if path == "/api/transactions":
            return transactions_payload(
                database,
                period,
                card,
                _first(query, "q", ""),
                month,
                _first(query, "category", ""),
                event_scope,
            ), 200
        return categories_payload(database, period, card, month, event_scope), 200
    if path == "/api/recurring":
        return recurring_payload(database, period, card, month), 200
    if path == "/api/observations":
        return observations_payload(
            database,
            period=period,
            card=card,
            month=month,
            income_hidden=_boolean_query(query, "income_hidden"),
        ), 200
    return events_payload(database, period, card, month), 200


def dispatch_json_post(database: Path, path: str, payload: dict) -> tuple[dict, int]:
    """Dispatch a decoded standard JSON mutation to its application service."""
    if path not in JSON_POST_PATHS:
        raise ValueError("Unknown JSON API route")
    if path == "/api/mapping":
        return save_mapping(
            database,
            str(payload.get("merchant_normalized", "")),
            str(payload.get("category", "")),
            str(payload.get("subcategory", "")),
        ), 200
    if path == "/api/merchants":
        aliases = payload.get("aliases", [])
        if not isinstance(aliases, list):
            raise ValueError("Aliases must be a list")
        return save_merchant(
            database,
            str(payload.get("canonical_group_id", "")),
            str(payload.get("display_name", "")),
            aliases,
        ), 200
    if path == "/api/transaction-category":
        return save_transaction_category(
            database,
            int(payload.get("transaction_id", 0)),
            str(payload.get("category", "")),
            str(payload.get("subcategory", "")),
        ), 200
    if path == "/api/transaction-adjustment":
        return save_transaction_adjustment(
            database,
            int(payload.get("transaction_id", 0)),
            float(payload.get("reimbursed_amount", 0) or 0),
            str(payload.get("reimbursement_date", "")),
            str(payload.get("note", "")),
            bool(payload.get("remove", False)),
        ), 200
    if path == "/api/transaction-event":
        return save_transaction_event(
            database,
            int(payload.get("transaction_id", 0)),
            str(payload.get("event_id", "")),
        ), 200
    if path == "/api/events":
        return create_event(
            database,
            str(payload.get("name", "")),
            str(payload.get("event_type", "")),
            str(payload.get("start_date", "")),
            str(payload.get("end_date", "")),
            payload.get("budget"),
            str(payload.get("status", "planned")),
            str(payload.get("destination", "")),
        ), 201
    if path == "/api/event-settings":
        return save_event_settings(
            database,
            str(payload.get("event_id", "")),
            str(payload.get("name", "")),
            str(payload.get("event_type", "")),
            str(payload.get("start_date", "")),
            str(payload.get("end_date", "")),
            payload.get("budget"),
            str(payload.get("status", "")),
            str(payload.get("destination", "")),
        ), 200
    if path == "/api/observation-review":
        return save_observation_review(
            database,
            str(payload.get("finding_key", "")),
            str(payload.get("observation_type", "")),
            str(payload.get("resolution", "")),
            str(payload.get("month", "")),
            payload.get("transaction_ids", []),
            str(payload.get("recurring_series_id", "")),
            str(payload.get("occurrence_start", "")),
            str(payload.get("occurrence_end", "")),
            str(payload.get("merchant_label", "")),
            bool(payload.get("remove", False)),
        ), 200
    if path == "/api/recurring-profile":
        return save_recurring_profile(
            database,
            str(payload.get("canonical_group_id", "")),
            str(payload.get("recurring_type", "")),
            str(payload.get("cadence", "")),
            str(payload.get("lifecycle_status", "")),
            str(payload.get("end_month", "")),
        ), 200
    included_aliases = payload.get("included_aliases")
    return manage_recurring_profile(
        database,
        str(payload.get("canonical_group_id", "")),
        str(payload.get("verdict", "")),
        str(payload.get("recurring_type", "")),
        str(payload.get("cadence", "")),
        str(payload.get("lifecycle_status", "active")),
        str(payload.get("end_month", "")),
        included_aliases if isinstance(included_aliases, list) else None,
    ), 200
