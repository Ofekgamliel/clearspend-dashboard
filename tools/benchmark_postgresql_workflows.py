#!/usr/bin/env python3
"""Compare representative SQLite and PostgreSQL read-workflow timings safely."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator

from clearspend.database.postgresql import PostgreSQLPool
from clearspend.database.runtime_config import load_postgresql_runtime_configuration
from clearspend.observations.payloads import observations_payload
from clearspend.reporting.dashboard import dashboard_payload
from clearspend.transactions.queries import transactions_payload


Workflow = Callable[[object], object]


class _CountingConnection:
    def __init__(self, connection: Any, pool: "_CountingPostgreSQLPool") -> None:
        self._connection = connection
        self._pool = pool

    def execute(self, sql: Any, parameters: Any = None) -> Any:
        self._pool.query_count += 1
        if parameters is None:
            return self._connection.execute(sql)
        return self._connection.execute(sql, parameters)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._connection, name)


class _CountingPostgreSQLPool(PostgreSQLPool):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.query_count = 0

    @contextmanager
    def connection(self) -> Iterator[_CountingConnection]:
        with super().connection() as connection:
            yield _CountingConnection(connection, self)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _milliseconds(workflow: Workflow, database: object) -> float:
    started = time.perf_counter()
    workflow(database)
    return round((time.perf_counter() - started) * 1000, 1)


def _workflows(sqlite_database: Path) -> list[tuple[str, Workflow]]:
    all_dashboard = dashboard_payload(sqlite_database, "all", "all")
    all_transactions = transactions_payload(sqlite_database, "all", "all")
    months = [str(value) for value in all_dashboard.get("available_months", ())]
    cards = [
        str(item["key"])
        for item in all_dashboard.get("cards", ())
        if item.get("key")
    ]
    rows = all_transactions.get("transactions", ())
    if not months or not cards or not rows:
        raise RuntimeError("Representative performance probes are unavailable")

    latest_month = months[0]
    changed_month = months[len(months) // 2]
    selected_card = cards[0]
    search_text = str(rows[0].get("merchant_raw") or "").strip()
    if not search_text:
        raise RuntimeError("Representative transaction search probe is unavailable")

    return [
        (
            "dashboard_initial_load",
            lambda database: dashboard_payload(database, "month", "all"),
        ),
        (
            "dashboard_month_change",
            lambda database: dashboard_payload(
                database, "month", "all", changed_month,
            ),
        ),
        (
            "dashboard_card_change",
            lambda database: dashboard_payload(
                database, "month", selected_card, latest_month,
            ),
        ),
        (
            "transaction_search",
            lambda database: transactions_payload(
                database, "all", "all", search=search_text,
            ),
        ),
        (
            "financial_observations",
            lambda database: observations_payload(
                database, period="month", card="all", month=latest_month,
            ),
        ),
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("sqlite_database", type=Path)
    parser.add_argument("--postgresql-config", required=True, type=Path)
    args = parser.parse_args()

    sqlite_database = args.sqlite_database.resolve()
    source_before = (sqlite_database.stat().st_size, _sha256(sqlite_database))
    workflows = _workflows(sqlite_database)
    configuration = load_postgresql_runtime_configuration(
        args.postgresql_config.resolve()
    )
    pool = _CountingPostgreSQLPool(configuration.database)
    pool.open()
    try:
        timings = []
        for name, workflow in workflows:
            sqlite_ms = _milliseconds(workflow, sqlite_database)
            pool.query_count = 0
            postgresql_ms = _milliseconds(workflow, pool)
            timings.append(
                {
                    "workflow": name,
                    "sqlite_ms": sqlite_ms,
                    "postgresql_ms": postgresql_ms,
                    "postgresql_queries": pool.query_count,
                }
            )
    finally:
        pool.close()

    source_after = (sqlite_database.stat().st_size, _sha256(sqlite_database))
    print(json.dumps(
        {
            "status": "measured",
            "sqlite_source_unchanged": source_before == source_after,
            "timings": timings,
        },
        indent=2,
        sort_keys=True,
    ))


if __name__ == "__main__":
    main()
