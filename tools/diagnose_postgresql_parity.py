#!/usr/bin/env python3
"""Report safe field-level parity diagnostics without printing private values."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

from clearspend.database.postgresql import PostgreSQLPool
from clearspend.database.runtime_config import load_postgresql_runtime_configuration
from clearspend.reporting.dashboard import dashboard_payload
from clearspend.transactions.queries import transactions_payload


def _row_differences(
    sqlite_rows: Sequence[Mapping[str, Any]],
    postgresql_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    sqlite_by_id = {row.get("id"): row for row in sqlite_rows}
    postgresql_by_id = {row.get("id"): row for row in postgresql_rows}
    unequal: Counter[str] = Counter()
    type_only: Counter[str] = Counter()
    for row_id in sqlite_by_id.keys() & postgresql_by_id.keys():
        sqlite_row = sqlite_by_id[row_id]
        postgresql_row = postgresql_by_id[row_id]
        for field in sqlite_row.keys() | postgresql_row.keys():
            sqlite_value = sqlite_row.get(field)
            postgresql_value = postgresql_row.get(field)
            if sqlite_value != postgresql_value:
                unequal[field] += 1
            elif type(sqlite_value) is not type(postgresql_value):
                type_only[field] += 1
    return {
        "sqlite_rows": len(sqlite_rows),
        "postgresql_rows": len(postgresql_rows),
        "same_ids": set(sqlite_by_id) == set(postgresql_by_id),
        "same_order": [row.get("id") for row in sqlite_rows]
        == [row.get("id") for row in postgresql_rows],
        "unequal_fields": dict(sorted(unequal.items())),
        "type_only_fields": dict(sorted(type_only.items())),
    }


def _mapping_differences(
    sqlite_values: Mapping[str, Any],
    postgresql_values: Mapping[str, Any],
) -> dict[str, list[str]]:
    unequal = []
    type_only = []
    for field in sorted(sqlite_values.keys() | postgresql_values.keys()):
        sqlite_value = sqlite_values.get(field)
        postgresql_value = postgresql_values.get(field)
        if sqlite_value != postgresql_value:
            unequal.append(field)
        elif type(sqlite_value) is not type(postgresql_value):
            type_only.append(field)
    return {"unequal_fields": unequal, "type_only_fields": type_only}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("sqlite_database", type=Path)
    parser.add_argument("--postgresql-config", required=True, type=Path)
    parser.add_argument("--month-index", type=int)
    args = parser.parse_args()
    configuration = load_postgresql_runtime_configuration(
        args.postgresql_config.resolve()
    )
    pool = PostgreSQLPool(configuration.database)
    pool.open()
    try:
        sqlite_transactions = transactions_payload(
            args.sqlite_database, "all", "all"
        )["transactions"]
        postgresql_transactions = transactions_payload(
            pool, "all", "all"
        )["transactions"]
        sqlite_dashboard = dashboard_payload(args.sqlite_database, "all", "all")
        postgresql_dashboard = dashboard_payload(pool, "all", "all")
        report = {
            "all_transactions": _row_differences(
                sqlite_transactions, postgresql_transactions,
            ),
            "all_dashboard_metrics": _mapping_differences(
                sqlite_dashboard["metrics"], postgresql_dashboard["metrics"],
            ),
            "all_dashboard_income": _mapping_differences(
                sqlite_dashboard["income_summary"],
                postgresql_dashboard["income_summary"],
            ),
            "all_dashboard_recent": _row_differences(
                sqlite_dashboard["recent_transactions"],
                postgresql_dashboard["recent_transactions"],
            ),
        }
        if args.month_index is not None:
            months = sqlite_dashboard["available_months"]
            if args.month_index < 1 or args.month_index > len(months):
                parser.error("--month-index is outside the available month range")
            month = months[args.month_index - 1]
            sqlite_month = dashboard_payload(
                args.sqlite_database, "month", "all", month,
            )
            postgresql_month = dashboard_payload(pool, "month", "all", month)
            report["selected_month_dashboard_metrics"] = _mapping_differences(
                sqlite_month["metrics"], postgresql_month["metrics"],
            )
            sqlite_metrics = sqlite_month["metrics"]
            postgresql_metrics = postgresql_month["metrics"]
            report["selected_month_daily_average"] = {
                "same_displayed_spent": (
                    sqlite_metrics["spent"] == postgresql_metrics["spent"]
                ),
                "same_active_days": (
                    sqlite_metrics["active_days"]
                    == postgresql_metrics["active_days"]
                ),
                "sqlite_matches_displayed_spent_formula": (
                    sqlite_metrics["daily_average"]
                    == round(
                        sqlite_metrics["spent"] / sqlite_metrics["active_days"], 2
                    )
                ),
                "postgresql_matches_displayed_spent_formula": (
                    postgresql_metrics["daily_average"]
                    == round(
                        postgresql_metrics["spent"]
                        / postgresql_metrics["active_days"], 2
                    )
                ),
            }
    finally:
        pool.close()
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
