"""Safe cross-engine financial and presentation parity verification."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal
from numbers import Number
from typing import Any, Mapping, Sequence

from clearspend.database.connection import DatabaseTarget
from clearspend.observations.payloads import observations_payload
from clearspend.reporting.dashboard import dashboard_payload
from clearspend.transactions.queries import transactions_payload


DASHBOARD_SECTIONS = (
    "period",
    "selected_card",
    "metrics",
    "income_summary",
    "cards",
    "categories",
    "category_comparison",
    "recent_transactions",
    "trend",
    "trend_mode",
    "purchase_activity_summary",
    "insights",
    "latest_import",
    "available_months",
)


class FinancialParityError(RuntimeError):
    """Raised when SQLite and PostgreSQL produce different user-facing data."""


@dataclass(frozen=True)
class FinancialParityReport:
    comparisons: int
    snapshot_sha256: str


@dataclass(frozen=True)
class _ParityProbes:
    months: tuple[str, ...]
    cards: tuple[str, ...]
    search_text: str
    category: str


def _canonical_value(value: object) -> object:
    if isinstance(value, Mapping):
        return {
            str(key): _canonical_value(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_canonical_value(item) for item in value]
    if isinstance(value, Number) and not isinstance(value, bool):
        number = Decimal(str(value))
        normalized = "0" if number == 0 else format(number.normalize(), "f")
        return {"__clearspend_number__": normalized}
    return value


def _canonical_json(value: object) -> str:
    return json.dumps(
        _canonical_value(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _dashboard_entries(
    entries: dict[str, str],
    name: str,
    payload: Mapping[str, Any],
) -> None:
    for section in DASHBOARD_SECTIONS:
        entries[f"{name}:{section}"] = _digest(payload.get(section))


def _source_probes(source: DatabaseTarget) -> _ParityProbes:
    all_dashboard = dashboard_payload(source, "all", "all")
    all_transactions = transactions_payload(source, "all", "all")
    cards = tuple(sorted({
        str(item.get("key"))
        for item in all_dashboard.get("cards", ())
        if item.get("key")
    }))
    rows: Sequence[Mapping[str, Any]] = all_transactions.get("transactions", ())
    search_text = ""
    category = ""
    if rows:
        search_text = str(rows[0].get("merchant_raw") or "")
        category = str(rows[0].get("category") or "")
    return _ParityProbes(
        months=tuple(str(month) for month in all_dashboard.get("available_months", ())),
        cards=cards,
        search_text=search_text,
        category=category,
    )


def _financial_snapshot(
    database: DatabaseTarget,
    probes: _ParityProbes,
) -> dict[str, str]:
    entries: dict[str, str] = {}
    representative_months = frozenset(
        probes.months[index]
        for index in {0, len(probes.months) // 2, len(probes.months) - 1}
        if probes.months
    )
    for period in ("year", "all"):
        dashboard = dashboard_payload(database, period, "all")
        _dashboard_entries(entries, f"dashboard:{period}:all", dashboard)
        entries[f"transactions:{period}:all"] = _digest(
            transactions_payload(database, period, "all")
        )
        entries[f"observations:{period}:all"] = _digest(
            observations_payload(database, period=period, card="all")
        )
        for card_index, card in enumerate(probes.cards, start=1):
            _dashboard_entries(
                entries,
                f"dashboard:{period}:card-{card_index}",
                dashboard_payload(database, period, card),
            )
            entries[f"transactions:{period}:card-{card_index}"] = _digest(
                transactions_payload(database, period, card)
            )

    for month_index, month in enumerate(probes.months, start=1):
        dashboard = dashboard_payload(database, "month", "all", month)
        _dashboard_entries(entries, f"dashboard:month-{month_index}:all", dashboard)
        entries[f"transactions:month-{month_index}:all"] = _digest(
            transactions_payload(database, "month", "all", month=month)
        )
        if month in representative_months:
            entries[f"observations:month-{month_index}:all"] = _digest(
                observations_payload(
                    database, period="month", card="all", month=month,
                )
            )
            for card_index, card in enumerate(probes.cards, start=1):
                _dashboard_entries(
                    entries,
                    f"dashboard:month-{month_index}:card-{card_index}",
                    dashboard_payload(database, "month", card, month),
                )
                entries[f"transactions:month-{month_index}:card-{card_index}"] = _digest(
                    transactions_payload(database, "month", card, month=month)
                )

    if probes.search_text:
        entries["transactions:all:search"] = _digest(
            transactions_payload(
                database, "all", "all", search=probes.search_text,
            )
        )
    if probes.category:
        entries["transactions:all:category"] = _digest(
            transactions_payload(
                database, "all", "all", category=probes.category,
            )
        )
    return entries


def verify_financial_parity(
    sqlite_source: DatabaseTarget,
    postgresql_target: DatabaseTarget,
) -> FinancialParityReport:
    """Compare user-facing transaction and calculated payloads exactly.

    The raised error lists only stable workflow names. It never includes query
    probes, financial values, transaction fields, or payload fragments.
    """
    probes = _source_probes(sqlite_source)
    sqlite_snapshot = _financial_snapshot(sqlite_source, probes)
    postgresql_snapshot = _financial_snapshot(postgresql_target, probes)
    changed = sorted(
        name
        for name in set(sqlite_snapshot) | set(postgresql_snapshot)
        if sqlite_snapshot.get(name) != postgresql_snapshot.get(name)
    )
    if changed:
        raise FinancialParityError(
            "Financial/API parity failed for: " + ", ".join(changed)
        )
    return FinancialParityReport(
        comparisons=len(sqlite_snapshot),
        snapshot_sha256=_digest(sqlite_snapshot),
    )
