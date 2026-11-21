from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from clearspend.database.connection import database_connection, database_transaction
from clearspend.database.postgresql import PostgreSQLPool
from clearspend.events.queries import events_payload
from clearspend.events.service import (
    create_event,
    save_event_settings,
    save_transaction_event,
)
from clearspend.observations.queries import observation_reviews_payload
from clearspend.observations.service import save_observation_review
from clearspend.observations.inputs import load_observation_inputs
from clearspend.recurring.queries import recurring_payload
from clearspend.recurring.service import manage_recurring_profile, save_recurring_profile
from clearspend.reporting.category_queries import categories_payload
from clearspend.reporting.dashboard import dashboard_payload
from clearspend.merchants.queries import mapping_payload, merchants_payload
from clearspend.merchants.service import save_merchant
from clearspend.transactions.queries import transactions_payload
from clearspend.transactions.service import (
    save_transaction_adjustment,
    save_transaction_category,
)
from clearspend.staging.coverage import save_import_coverage, staged_statement_coverage
from clearspend.staging.duplicates import possible_duplicate_matches
from clearspend.staging.references import staged_reference_data


def run_observation_review_smoke(pool: PostgreSQLPool) -> dict:
    """Exercise the first PostgreSQL feature slice and remove its synthetic rows."""
    token = uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    finding_key = f"POSSIBLE DUPLICATE:synthetic:{token}"
    import_id = None
    transaction_ids: list[int] = []
    try:
        with database_transaction(pool) as connection:
            import_id = connection.execute(
                """INSERT INTO imports(
                original_name,source_path,byte_hash,source_format,status,imported_at
                ) VALUES(?,?,?,?,?,?) RETURNING id""",
                (
                    "synthetic-postgresql-smoke.csv",
                    "synthetic://postgresql-smoke",
                    f"synthetic-{token}",
                    "synthetic",
                    "smoke-test",
                    now,
                ),
            ).fetchone()["id"]
            for occurrence in (1, 2):
                transaction_id = connection.execute(
                    """INSERT INTO transactions(
                    transaction_key,base_key,occurrence,provider,card_last4,
                    source_sheet,merchant_raw,merchant_normalized,charged_amount,
                    charged_currency,first_import_id,created_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?) RETURNING id""",
                    (
                        f"synthetic-transaction-{token}-{occurrence}",
                        f"synthetic-base-{token}",
                        occurrence,
                        "synthetic",
                        "0000",
                        "synthetic",
                        "Synthetic Merchant",
                        "synthetic merchant",
                        "1.00",
                        "ILS",
                        import_id,
                        now,
                    ),
                ).fetchone()["id"]
                transaction_ids.append(int(transaction_id))

        saved = save_observation_review(
            pool,
            finding_key,
            "POSSIBLE DUPLICATE",
            "not_duplicate",
            "2000-01",
            transaction_ids,
        )
        reviews = observation_reviews_payload(pool)["reviews"]
        matching_reviews = [
            review for review in reviews if review["finding_key"] == finding_key
        ]
        if len(matching_reviews) != 1:
            raise RuntimeError("PostgreSQL observation-review smoke read failed")
        removed = save_observation_review(
            pool,
            finding_key,
            "POSSIBLE DUPLICATE",
            "not_duplicate",
            "2000-01",
            transaction_ids,
            remove=True,
        )
        if not removed["changed"]:
            raise RuntimeError("PostgreSQL observation-review smoke undo failed")
        return {
            "saved": saved["status"] == "reviewed",
            "read": True,
            "undone": True,
        }
    finally:
        with database_transaction(pool) as connection:
            connection.execute(
                "DELETE FROM observation_reviews WHERE finding_key=?",
                (finding_key,),
            )
            if transaction_ids:
                placeholders = ",".join("?" for _ in transaction_ids)
                connection.execute(
                    f"DELETE FROM transactions WHERE id IN ({placeholders})",
                    transaction_ids,
                )
            if import_id is not None:
                connection.execute("DELETE FROM imports WHERE id=?", (import_id,))


def run_transaction_smoke(pool: PostgreSQLPool) -> dict:
    """Exercise transaction search and corrections, then remove synthetic rows."""
    token = uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    import_id = None
    transaction_id = None
    try:
        with database_transaction(pool) as connection:
            import_id = connection.execute(
                """INSERT INTO imports(
                original_name,source_path,byte_hash,source_format,status,imported_at
                ) VALUES(?,?,?,?,?,?) RETURNING id""",
                (
                    "synthetic-transaction-smoke.csv",
                    "synthetic://transaction-smoke",
                    f"synthetic-transaction-{token}",
                    "synthetic",
                    "smoke-test",
                    now,
                ),
            ).fetchone()["id"]
            transaction_id = connection.execute(
                """INSERT INTO transactions(
                transaction_key,base_key,occurrence,provider,card_last4,
                source_sheet,transaction_date,billing_month,billing_month_source,
                merchant_raw,merchant_normalized,charged_amount,charged_currency,
                user_category,first_import_id,created_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) RETURNING id""",
                (
                    f"synthetic-transaction-{token}",
                    f"synthetic-base-{token}",
                    1,
                    "synthetic",
                    "0000",
                    "synthetic",
                    "2000-01-10",
                    "2000-01",
                    "synthetic",
                    f"Synthetic Search {token.upper()}",
                    f"synthetic search {token}",
                    "100.00",
                    "ILS",
                    "Original category",
                    import_id,
                    now,
                ),
            ).fetchone()["id"]

        category = save_transaction_category(
            pool,
            int(transaction_id),
            "Synthetic override",
            "One transaction",
        )
        adjustment = save_transaction_adjustment(
            pool,
            int(transaction_id),
            25.0,
            "2000-01-15",
            "Synthetic reimbursement",
        )
        payload = transactions_payload(
            pool,
            "all",
            "all",
            search=token.lower(),
        )
        matches = [
            row for row in payload["transactions"] if row["id"] == transaction_id
        ]
        if len(matches) != 1:
            raise RuntimeError("PostgreSQL transaction smoke search failed")
        row = matches[0]
        if row["category"] != "Synthetic override":
            raise RuntimeError("PostgreSQL transaction category smoke failed")
        if round(float(row["personal_amount"]), 2) != 75.0:
            raise RuntimeError("PostgreSQL reimbursement smoke failed")
        return {
            "category": category["status"] == "saved",
            "adjustment": adjustment["status"] == "saved",
            "search": True,
            "personal_amount": True,
        }
    finally:
        with database_transaction(pool) as connection:
            if transaction_id is not None:
                connection.execute(
                    "DELETE FROM transaction_category_overrides WHERE transaction_id=?",
                    (transaction_id,),
                )
                connection.execute(
                    "DELETE FROM transaction_spending_adjustments WHERE transaction_id=?",
                    (transaction_id,),
                )
                connection.execute(
                    "DELETE FROM transactions WHERE id=?",
                    (transaction_id,),
                )
            if import_id is not None:
                connection.execute("DELETE FROM imports WHERE id=?", (import_id,))


def run_merchant_smoke(pool: PostgreSQLPool) -> dict:
    """Exercise merchant identity, category history, and future-rule application."""
    token = uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    group_id = f"synthetic-group-{token}"
    aliases = [f"synthetic merchant {token} alpha", f"synthetic merchant {token} beta"]
    import_id = None
    transaction_ids: list[int] = []
    try:
        with database_transaction(pool) as connection:
            import_id = connection.execute(
                """INSERT INTO imports(
                original_name,source_path,byte_hash,source_format,status,imported_at
                ) VALUES(?,?,?,?,?,?) RETURNING id""",
                (
                    "synthetic-merchant-smoke.csv",
                    "synthetic://merchant-smoke",
                    f"synthetic-merchant-{token}",
                    "synthetic",
                    "smoke-test",
                    now,
                ),
            ).fetchone()["id"]
            for index, alias in enumerate(aliases, start=1):
                transaction_ids.append(int(connection.execute(
                    """INSERT INTO transactions(
                    transaction_key,base_key,occurrence,provider,card_last4,
                    source_sheet,transaction_date,merchant_raw,merchant_normalized,
                    charged_amount,charged_currency,user_category,first_import_id,created_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?) RETURNING id""",
                    (
                        f"synthetic-merchant-{token}-{index}",
                        f"synthetic-merchant-base-{token}-{index}",
                        1,
                        "synthetic",
                        "0000",
                        "synthetic",
                        f"2000-01-{index:02d}",
                        alias.title(),
                        alias,
                        "10.00",
                        "ILS",
                        f"Original {index}",
                        import_id,
                        now,
                    ),
                ).fetchone()["id"]))
            for alias in aliases:
                connection.execute(
                    """INSERT INTO merchant_display_mappings(
                    merchant_normalized,canonical_group_id,display_name,updated_at
                    ) VALUES(?,?,?,?)""",
                    (alias, group_id, "Old Synthetic Group", now),
                )
            connection.execute(
                """INSERT INTO import_coverage(
                import_id,card_last4,statement_month,finalized_rows,official_total
                ) VALUES(?,?,?,?,?)""",
                (import_id, "0000", "2000-01", 2, "20.00"),
            )

        saved = save_merchant(
            pool,
            group_id,
            "Synthetic Group",
            [{
                "merchant_normalized": aliases[0],
                "category": "Synthetic category",
                "subcategory": "Exact alias",
            }],
        )
        with database_transaction(pool) as connection:
            transaction_ids.append(int(connection.execute(
                """INSERT INTO transactions(
                transaction_key,base_key,occurrence,provider,card_last4,
                source_sheet,transaction_date,merchant_raw,merchant_normalized,
                charged_amount,charged_currency,user_category,first_import_id,created_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?) RETURNING id""",
                (
                    f"synthetic-merchant-{token}-future",
                    f"synthetic-merchant-base-{token}-future",
                    1,
                    "synthetic",
                    "0000",
                    "synthetic",
                    "2000-01-03",
                    aliases[0].title(),
                    aliases[0],
                    "10.00",
                    "ILS",
                    "Should be replaced",
                    import_id,
                    now,
                ),
            ).fetchone()["id"]))
            future = connection.execute(
                """SELECT user_category,user_subcategory FROM transactions
                WHERE id=?""",
                (transaction_ids[-1],),
            ).fetchone()

        payload = merchants_payload(pool)
        mapping = mapping_payload(pool)
        matching = [
            merchant for merchant in payload["merchants"]
            if merchant["canonical_group_id"] == group_id
        ]
        if len(matching) != 1 or matching[0]["display_name"] != "Synthetic Group":
            raise RuntimeError("PostgreSQL merchant display-identity smoke failed")
        if future["user_category"] != "Synthetic category":
            raise RuntimeError("PostgreSQL future merchant-rule smoke failed")
        if future["user_subcategory"] != "Exact alias":
            raise RuntimeError("PostgreSQL future merchant-subcategory smoke failed")
        imported = [
            item for item in mapping["recent_imports"] if item["id"] == import_id
        ]
        if len(imported) != 1 or len(imported[0]["coverage"]) != 1:
            raise RuntimeError("PostgreSQL merchant mapping-context smoke failed")
        return {
            "identity": True,
            "historical_category": saved["transactions_updated"] == 1,
            "future_category": True,
            "independent_aliases": matching[0]["transactions"] == 3,
            "mapping_context": True,
        }
    finally:
        with database_transaction(pool) as connection:
            connection.execute(
                "DELETE FROM recurring_profile_members WHERE canonical_group_id=?",
                (group_id,),
            )
            connection.execute(
                "DELETE FROM recurring_profiles WHERE canonical_group_id=?",
                (group_id,),
            )
            connection.execute(
                "DELETE FROM merchant_mappings WHERE merchant_normalized=ANY(?)",
                (aliases,),
            )
            connection.execute(
                "DELETE FROM merchant_display_mappings WHERE merchant_normalized=ANY(?)",
                (aliases,),
            )
            if transaction_ids:
                connection.execute(
                    "DELETE FROM transactions WHERE id=ANY(?)",
                    (transaction_ids,),
                )
            if import_id is not None:
                connection.execute("DELETE FROM imports WHERE id=?", (import_id,))


def run_event_smoke(pool: PostgreSQLPool) -> dict:
    """Exercise event settings and exact membership, then remove synthetic rows."""
    token = uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    import_id = None
    transaction_id = None
    event_id = None
    try:
        with database_transaction(pool) as connection:
            import_id = connection.execute(
                """INSERT INTO imports(
                original_name,source_path,byte_hash,source_format,status,imported_at
                ) VALUES(?,?,?,?,?,?) RETURNING id""",
                (
                    "synthetic-event-smoke.csv",
                    "synthetic://event-smoke",
                    f"synthetic-event-{token}",
                    "synthetic",
                    "smoke-test",
                    now,
                ),
            ).fetchone()["id"]
            transaction_id = int(connection.execute(
                """INSERT INTO transactions(
                transaction_key,base_key,occurrence,provider,card_last4,
                source_sheet,transaction_date,billing_month,billing_month_source,
                merchant_raw,merchant_normalized,charged_amount,charged_currency,
                user_category,first_import_id,created_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) RETURNING id""",
                (
                    f"synthetic-event-{token}",
                    f"synthetic-event-base-{token}",
                    1,
                    "synthetic",
                    "0000",
                    "synthetic",
                    "2000-01-15",
                    "2000-01",
                    "synthetic",
                    "Synthetic Event Merchant",
                    f"synthetic event merchant {token}",
                    "80.00",
                    "ILS",
                    "Synthetic category",
                    import_id,
                    now,
                ),
            ).fetchone()["id"])

        created = create_event(
            pool,
            "Synthetic event",
            "trip",
            "2000-01-01",
            "2000-01-31",
            "500",
            "planned",
        )
        event_id = created["event"]["id"]
        assigned = save_transaction_event(pool, transaction_id, event_id)
        payload = events_payload(pool, "month", "all", "2000-01")
        matching = [event for event in payload["events"] if event["id"] == event_id]
        if len(matching) != 1 or matching[0]["transaction_count"] != 1:
            raise RuntimeError("PostgreSQL event read smoke failed")
        save_event_settings(
            pool,
            event_id,
            "Synthetic event edited",
            "other",
            "2001-01-01",
            "2001-01-02",
            "250",
            "completed",
        )
        with database_transaction(pool) as connection:
            membership = connection.execute(
                """SELECT COUNT(*) AS count FROM event_transactions
                WHERE transaction_id=? AND event_id=?""",
                (transaction_id, event_id),
            ).fetchone()["count"]
        if membership != 1:
            raise RuntimeError("PostgreSQL exact event membership smoke failed")
        unassigned = save_transaction_event(pool, transaction_id, "")
        return {
            "created": created["status"] == "created",
            "assigned": assigned["status"] == "assigned",
            "read": True,
            "membership_preserved": True,
            "unassigned": unassigned["status"] == "unassigned",
        }
    finally:
        with database_transaction(pool) as connection:
            if transaction_id is not None:
                connection.execute(
                    "DELETE FROM event_transactions WHERE transaction_id=?",
                    (transaction_id,),
                )
            if event_id is not None:
                connection.execute("DELETE FROM events WHERE id=?", (event_id,))
            if transaction_id is not None:
                connection.execute("DELETE FROM transactions WHERE id=?", (transaction_id,))
            if import_id is not None:
                connection.execute("DELETE FROM imports WHERE id=?", (import_id,))


def run_recurring_smoke(pool: PostgreSQLPool) -> dict:
    """Exercise recurring alias selection and lifecycle, then clean up."""
    token = uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    group_id = f"synthetic-recurring-{token}"
    aliases = [f"synthetic recurring {token} one", f"synthetic recurring {token} two"]
    import_id = None
    transaction_ids: list[int] = []
    try:
        with database_transaction(pool) as connection:
            import_id = connection.execute(
                """INSERT INTO imports(
                original_name,source_path,byte_hash,source_format,status,imported_at
                ) VALUES(?,?,?,?,?,?) RETURNING id""",
                (
                    "synthetic-recurring-smoke.csv",
                    "synthetic://recurring-smoke",
                    f"synthetic-recurring-{token}",
                    "synthetic",
                    "smoke-test",
                    now,
                ),
            ).fetchone()["id"]
            rows = (
                (aliases[0], "2000-01", "50.00"),
                (aliases[0], "2000-02", "55.00"),
                (aliases[1], "2000-02", "80.00"),
            )
            for index, (alias, month, amount) in enumerate(rows, start=1):
                transaction_ids.append(int(connection.execute(
                    """INSERT INTO transactions(
                    transaction_key,base_key,occurrence,provider,card_last4,
                    source_sheet,transaction_date,billing_month,billing_month_source,
                    merchant_raw,merchant_normalized,charged_amount,charged_currency,
                    user_category,first_import_id,created_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) RETURNING id""",
                    (
                        f"synthetic-recurring-{token}-{index}",
                        f"synthetic-recurring-base-{token}-{index}",
                        1,
                        "synthetic",
                        "0000",
                        "synthetic",
                        f"{month}-10",
                        month,
                        "synthetic",
                        alias.title(),
                        alias,
                        amount,
                        "ILS",
                        "Synthetic recurring",
                        import_id,
                        now,
                    ),
                ).fetchone()["id"]))
            for alias in aliases:
                connection.execute(
                    """INSERT INTO merchant_display_mappings(
                    merchant_normalized,canonical_group_id,display_name,updated_at
                    ) VALUES(?,?,?,?)""",
                    (alias, group_id, "Synthetic Recurring", now),
                )

        profile = manage_recurring_profile(
            pool,
            group_id,
            "recurring",
            "Fixed recurring",
            "Monthly",
            "active",
            "",
            [aliases[0]],
        )
        payload = recurring_payload(pool, "month", "all", "2000-02")
        matching = [
            item for item in payload["series"]
            if item["canonical_group_id"] == group_id
        ]
        if len(matching) != 1 or payload["metrics"]["recurring_billed"] != 55.0:
            raise RuntimeError("PostgreSQL recurring read smoke failed")
        if matching[0]["source_aliases"] != [aliases[0].title()]:
            raise RuntimeError("PostgreSQL recurring alias-selection smoke failed")
        ended = save_recurring_profile(
            pool,
            group_id,
            "Fixed recurring",
            "Monthly",
            "ended",
            "2000-02",
        )
        removed = manage_recurring_profile(pool, group_id, "not_recurring")
        if removed["included_aliases"] != [aliases[0]]:
            raise RuntimeError("PostgreSQL recurring membership preservation failed")
        return {
            "profile": profile["verdict"] == "recurring",
            "selected_alias": True,
            "read": True,
            "lifecycle": ended["end_month"] == "2000-02",
            "membership_preserved": True,
        }
    finally:
        with database_transaction(pool) as connection:
            connection.execute(
                "DELETE FROM recurring_profile_members WHERE canonical_group_id=?",
                (group_id,),
            )
            connection.execute(
                "DELETE FROM recurring_profiles WHERE canonical_group_id=?",
                (group_id,),
            )
            connection.execute(
                "DELETE FROM merchant_display_mappings WHERE merchant_normalized=ANY(?)",
                (aliases,),
            )
            if transaction_ids:
                connection.execute(
                    "DELETE FROM transactions WHERE id=ANY(?)",
                    (transaction_ids,),
                )
            if import_id is not None:
                connection.execute("DELETE FROM imports WHERE id=?", (import_id,))


def run_category_smoke(pool: PostgreSQLPool) -> dict:
    """Exercise category comparison, card, and event scope, then clean up."""
    token = uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    event_id = f"synthetic-category-event-{token}"
    import_id = None
    transaction_ids: list[int] = []
    try:
        with database_transaction(pool) as connection:
            import_id = connection.execute(
                """INSERT INTO imports(
                original_name,source_path,byte_hash,source_format,status,imported_at
                ) VALUES(?,?,?,?,?,?) RETURNING id""",
                (
                    "synthetic-category-smoke.csv",
                    "synthetic://category-smoke",
                    f"synthetic-category-{token}",
                    "synthetic",
                    "smoke-test",
                    now,
                ),
            ).fetchone()["id"]
            rows = (
                ("2000-01", "Synthetic Alpha", "Category Alpha", "100.00", "0001"),
                ("2000-02", "Synthetic Alpha", "Category Alpha", "150.00", "0001"),
                ("2000-02", "Synthetic Beta", "Category Beta", "50.00", "0002"),
            )
            for index, (month, merchant, category, amount, last4) in enumerate(rows, start=1):
                transaction_ids.append(int(connection.execute(
                    """INSERT INTO transactions(
                    transaction_key,base_key,occurrence,provider,card_last4,
                    source_sheet,transaction_date,billing_month,billing_month_source,
                    merchant_raw,merchant_normalized,charged_amount,charged_currency,
                    user_category,first_import_id,created_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) RETURNING id""",
                    (
                        f"synthetic-category-{token}-{index}",
                        f"synthetic-category-base-{token}-{index}",
                        1,
                        "synthetic",
                        last4,
                        "synthetic",
                        f"{month}-10",
                        month,
                        "synthetic",
                        merchant,
                        f"{merchant.lower()} {token}",
                        amount,
                        "ILS",
                        category,
                        import_id,
                        now,
                    ),
                ).fetchone()["id"]))
            connection.execute(
                """INSERT INTO events(
                id,name,event_type,start_date,end_date,status,created_at,updated_at
                ) VALUES(?,?,'other','2000-02-01','2000-02-28','completed',?,?)""",
                (event_id, "Synthetic category event", now, now),
            )
            connection.execute(
                """INSERT INTO event_transactions(transaction_id,event_id,assigned_at)
                VALUES(?,?,?)""",
                (transaction_ids[2], event_id, now),
            )

        all_spending = categories_payload(pool, "month", "all", "2000-02", "all")
        routine = categories_payload(pool, "month", "all", "2000-02", "routine")
        selected_card = categories_payload(
            pool, "month", "synthetic:0001", "2000-02", "all"
        )
        categories = {item["category"]: item for item in all_spending["categories"]}
        if all_spending["total"] != 200.0:
            raise RuntimeError("PostgreSQL category total smoke failed")
        if categories["Category Alpha"]["change_percent"] != 50:
            raise RuntimeError("PostgreSQL category comparison smoke failed")
        if categories["Category Beta"]["comparison"] != "new":
            raise RuntimeError("PostgreSQL new-category smoke failed")
        if routine["total"] != 150.0 or selected_card["total"] != 150.0:
            raise RuntimeError("PostgreSQL reporting-scope smoke failed")
        return {
            "totals": True,
            "comparison": True,
            "event_scope": True,
            "card_scope": True,
        }
    finally:
        with database_transaction(pool) as connection:
            connection.execute(
                "DELETE FROM event_transactions WHERE event_id=?",
                (event_id,),
            )
            connection.execute("DELETE FROM events WHERE id=?", (event_id,))
            if transaction_ids:
                connection.execute(
                    "DELETE FROM transactions WHERE id=ANY(?)",
                    (transaction_ids,),
                )
            if import_id is not None:
                connection.execute("DELETE FROM imports WHERE id=?", (import_id,))


def run_dashboard_smoke(pool: PostgreSQLPool) -> dict:
    """Exercise dashboard spending, income, cards, and trends, then clean up."""
    token = uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    import_id = None
    income_import_id = None
    transaction_ids: list[int] = []
    try:
        with database_transaction(pool) as connection:
            import_id = connection.execute(
                """INSERT INTO imports(
                original_name,source_path,byte_hash,source_format,status,imported_at
                ) VALUES(?,?,?,?,?,?) RETURNING id""",
                (
                    "synthetic-dashboard-smoke.csv",
                    "synthetic://dashboard-smoke",
                    f"synthetic-dashboard-{token}",
                    "synthetic",
                    "smoke-test",
                    now,
                ),
            ).fetchone()["id"]
            rows = (
                ("2000-01", "Synthetic January", "100.00", "Household"),
                ("2000-01", "Synthetic Refund", "-20.00", "Household"),
                ("2000-02", "Synthetic February", "150.00", "Travel"),
            )
            for index, (month, merchant, amount, category) in enumerate(rows, start=1):
                transaction_ids.append(int(connection.execute(
                    """INSERT INTO transactions(
                    transaction_key,base_key,occurrence,provider,card_last4,
                    source_sheet,transaction_date,billing_month,billing_month_source,
                    merchant_raw,merchant_normalized,charged_amount,charged_currency,
                    user_category,first_import_id,created_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) RETURNING id""",
                    (
                        f"synthetic-dashboard-{token}-{index}",
                        f"synthetic-dashboard-base-{token}-{index}",
                        1,
                        "synthetic",
                        "0000",
                        "synthetic",
                        f"{month}-{9 + index:02d}",
                        month,
                        "synthetic",
                        merchant,
                        f"{merchant.lower()} {token}",
                        amount,
                        "ILS",
                        category,
                        import_id,
                        now,
                    ),
                ).fetchone()["id"]))
            income_import_id = connection.execute(
                """INSERT INTO income_imports(
                original_name,source_path,byte_hash,source_format,status,imported_at
                ) VALUES(?,?,?,?,?,?) RETURNING id""",
                (
                    "synthetic-income-smoke.csv",
                    "synthetic://dashboard-income-smoke",
                    f"synthetic-income-{token}",
                    "synthetic",
                    "smoke-test",
                    now,
                ),
            ).fetchone()["id"]
            for month in ("2000-01", "2000-02"):
                connection.execute(
                    """INSERT INTO income_entries(
                    month,source_name,amount,entry_key,first_import_id,created_at
                    ) VALUES(?,?,?,?,?,?)""",
                    (
                        month,
                        "Synthetic income",
                        "500.00",
                        f"synthetic-income-{token}-{month}",
                        income_import_id,
                        now,
                    ),
                )

        month_payload = dashboard_payload(pool, "month", "all", "2000-02")
        year_payload = dashboard_payload(pool, "year", "all")
        if month_payload["metrics"]["spent"] != 150.0:
            raise RuntimeError("PostgreSQL dashboard spending smoke failed")
        if month_payload["income_summary"]["income"] != 500.0:
            raise RuntimeError("PostgreSQL dashboard income smoke failed")
        if month_payload["income_summary"]["remaining"] != 350.0:
            raise RuntimeError("PostgreSQL dashboard balance smoke failed")
        if month_payload["cards"][0]["amount"] != 150.0:
            raise RuntimeError("PostgreSQL dashboard card smoke failed")
        if month_payload["available_months"][:2] != ["2000-02", "2000-01"]:
            raise RuntimeError("PostgreSQL dashboard coverage smoke failed")
        trend = {item["bucket"]: item for item in year_payload["trend"]}
        if trend["2000-01"]["amount"] != 80.0 or trend["2000-02"]["income"] != 500.0:
            raise RuntimeError("PostgreSQL dashboard trend smoke failed")
        return {
            "spending": True,
            "income": True,
            "balance": True,
            "cards": True,
            "coverage": True,
            "trend": True,
        }
    finally:
        with database_transaction(pool) as connection:
            if income_import_id is not None:
                connection.execute(
                    "DELETE FROM income_entries WHERE first_import_id=?",
                    (income_import_id,),
                )
                connection.execute(
                    "DELETE FROM income_imports WHERE id=?",
                    (income_import_id,),
                )
            if transaction_ids:
                connection.execute(
                    "DELETE FROM transactions WHERE id=ANY(?)",
                    (transaction_ids,),
                )
            if import_id is not None:
                connection.execute("DELETE FROM imports WHERE id=?", (import_id,))


def run_observation_inputs_smoke(pool: PostgreSQLPool) -> dict:
    """Exercise composed observation inputs and installment identity, then clean up."""
    token = uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    finding_key = f"UNUSUAL TRANSACTION:synthetic-input-{token}"
    import_id = None
    income_import_id = None
    transaction_ids: list[int] = []
    try:
        with database_transaction(pool) as connection:
            import_id = connection.execute(
                """INSERT INTO imports(
                original_name,source_path,byte_hash,source_format,status,imported_at
                ) VALUES(?,?,?,?,?,?) RETURNING id""",
                (
                    "synthetic-observation-inputs.csv",
                    "synthetic://observation-inputs",
                    f"synthetic-observation-inputs-{token}",
                    "synthetic",
                    "smoke-test",
                    now,
                ),
            ).fetchone()["id"]
            transaction_ids.append(int(connection.execute(
                """INSERT INTO transactions(
                transaction_key,base_key,occurrence,provider,card_last4,source_sheet,
                transaction_date,billing_month,billing_month_source,merchant_raw,
                merchant_normalized,charged_amount,charged_currency,user_category,
                first_import_id,created_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) RETURNING id""",
                (
                    f"synthetic-input-{token}-jan",
                    f"synthetic-input-base-{token}-jan",
                    1, "synthetic", "0000", "synthetic", "2000-01-10", "2000-01",
                    "synthetic", "Synthetic January", f"synthetic january {token}",
                    "100.00", "ILS", "Household", import_id, now,
                ),
            ).fetchone()["id"]))
            transaction_ids.append(int(connection.execute(
                """INSERT INTO transactions(
                transaction_key,base_key,occurrence,provider,card_last4,source_sheet,
                transaction_date,billing_month,billing_month_source,merchant_raw,
                merchant_normalized,charged_amount,charged_currency,user_category,
                original_amount,original_currency,installment_number,installment_total,
                first_import_id,created_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) RETURNING id""",
                (
                    f"synthetic-input-{token}-feb",
                    f"synthetic-input-base-{token}-feb",
                    1, "synthetic", "0000", "synthetic", "2000-02-10", "2000-02",
                    "synthetic", "Synthetic Installment", f"synthetic installment {token}",
                    "40.00", "ILS", "Electronics", "120.00", "ILS", 1, 3,
                    import_id, now,
                ),
            ).fetchone()["id"]))
            income_import_id = connection.execute(
                """INSERT INTO income_imports(
                original_name,source_path,byte_hash,source_format,status,imported_at
                ) VALUES(?,?,?,?,?,?) RETURNING id""",
                (
                    "synthetic-observation-income.csv",
                    "synthetic://observation-income",
                    f"synthetic-observation-income-{token}",
                    "synthetic",
                    "smoke-test",
                    now,
                ),
            ).fetchone()["id"]
            for month in ("2000-01", "2000-02"):
                connection.execute(
                    """INSERT INTO income_entries(
                    month,source_name,amount,entry_key,first_import_id,created_at
                    ) VALUES(?,?,?,?,?,?)""",
                    (
                        month, "Synthetic observation income", "500.00",
                        f"synthetic-observation-income-{token}-{month}",
                        income_import_id, now,
                    ),
                )
            connection.execute(
                """INSERT INTO observation_reviews(
                finding_key,observation_type,resolution,month,transaction_ids,
                active,reviewed_at,updated_at
                ) VALUES(?,?,?,?,?,TRUE,?,?)""",
                (
                    finding_key, "UNUSUAL TRANSACTION", "not_unusual", "2000-02",
                    f"[{transaction_ids[1]}]", now, now,
                ),
            )

        snapshot = load_observation_inputs(
            pool,
            period="month",
            card="all",
            month="2000-02",
        )
        if snapshot.scope.history_months != ("2000-01", "2000-02"):
            raise RuntimeError("PostgreSQL observation history-scope smoke failed")
        if set(snapshot.transactions_by_month) != {"2000-01", "2000-02"}:
            raise RuntimeError("PostgreSQL observation transaction-input smoke failed")
        if not snapshot.income_visible or "2000-02" not in snapshot.household_history:
            raise RuntimeError("PostgreSQL observation income-input smoke failed")
        installment = snapshot.installments_by_month["2000-02"]
        if installment["installment_billed"] != 40.0 or len(installment["plans"]) != 1:
            raise RuntimeError("PostgreSQL observation installment-input smoke failed")
        if finding_key not in snapshot.reviewed_finding_keys:
            raise RuntimeError("PostgreSQL observation review-input smoke failed")
        return {
            "scope": True,
            "transactions": True,
            "income_visibility": True,
            "installments": True,
            "reviews": True,
        }
    finally:
        with database_transaction(pool) as connection:
            connection.execute(
                "DELETE FROM observation_reviews WHERE finding_key=?",
                (finding_key,),
            )
            if income_import_id is not None:
                connection.execute(
                    "DELETE FROM income_entries WHERE first_import_id=?",
                    (income_import_id,),
                )
                connection.execute(
                    "DELETE FROM income_imports WHERE id=?",
                    (income_import_id,),
                )
            if transaction_ids:
                connection.execute(
                    "DELETE FROM transactions WHERE id=ANY(?)",
                    (transaction_ids,),
                )
            if import_id is not None:
                connection.execute("DELETE FROM imports WHERE id=?", (import_id,))


def run_import_preview_smoke(pool: PostgreSQLPool) -> dict:
    """Exercise hosted preview references, duplicates, coverage, and linkage."""
    token = uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    merchant = f"synthetic preview {token}"
    import_id = None
    transaction_id = None
    try:
        with database_transaction(pool) as connection:
            import_id = connection.execute(
                """INSERT INTO imports(
                original_name,source_path,byte_hash,source_format,status,provider,
                card_last4,imported_at
                ) VALUES(?,?,?,?,?,?,?,?) RETURNING id""",
                (
                    "synthetic-preview.csv", "synthetic://preview",
                    f"synthetic-preview-{token}", "synthetic", "imported",
                    "synthetic", "0000", now,
                ),
            ).fetchone()["id"]
            transaction_id = int(connection.execute(
                """INSERT INTO transactions(
                transaction_key,base_key,occurrence,provider,card_last4,source_sheet,
                transaction_date,billing_month,billing_month_source,merchant_raw,
                merchant_normalized,charged_amount,charged_currency,user_category,
                first_import_id,created_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) RETURNING id""",
                (
                    f"synthetic-preview-key-{token}", f"synthetic-preview-base-{token}",
                    1, "synthetic", "0000", "synthetic", "2000-02-10", "2000-02",
                    "synthetic", "Synthetic Preview", merchant, "40.00", "ILS",
                    "Synthetic Preview Category", import_id, now,
                ),
            ).fetchone()["id"])
            connection.execute(
                """INSERT INTO merchant_mappings(
                merchant_normalized,category,updated_at
                ) VALUES(?,?,?)""",
                (merchant, "Synthetic Preview Category", now),
            )
            connection.execute(
                """INSERT INTO import_transactions(import_id,transaction_id,was_duplicate)
                VALUES(?,?,1)""",
                (import_id, transaction_id),
            )
            coverage = [{
                "card_last4": "0000", "statement_month": "2000-02",
                "statement_period": "2000-02", "statement_as_of_date": "2000-02-28",
                "purchase_date_from": "2000-02-10", "purchase_date_to": "2000-02-10",
                "billing_date_from": None, "billing_date_to": None,
                "finalized_rows": 1, "pending_rows": 0, "outside_cycle_rows": 0,
                "official_total": "40.00",
            }]
            save_import_coverage(connection, import_id, coverage)

        candidate = SimpleNamespace(
            provider="synthetic", card_last4="0000", transaction_date="2000-02-10",
            merchant_normalized=merchant, charged_amount="40.00", charged_currency="ILS",
            original_amount=None, original_currency=None,
            transaction_key=f"synthetic-preview-candidate-{token}", voucher_number=None,
            installment_number=None,
        )
        statement = SimpleNamespace(
            transactions=[SimpleNamespace(
                **candidate.__dict__,
                billing_date=None, source_sheet="synthetic", merchant_raw="Synthetic Preview",
            )],
            date_range="2000-02", statement_as_of_date="2000-02-28",
            official_total="40.00",
        )
        with database_connection(pool) as connection:
            categories, _identities = staged_reference_data(connection)
            matches, _reason = possible_duplicate_matches(connection, candidate)
            coverage, warnings = staged_statement_coverage(connection, statement)
            linkage = connection.execute(
                """SELECT was_duplicate FROM import_transactions
                WHERE import_id=? AND transaction_id=?""",
                (import_id, transaction_id),
            ).fetchone()
        if "Synthetic Preview Category" not in categories:
            raise RuntimeError("PostgreSQL staged reference smoke failed")
        if [row["id"] for row in matches] != [transaction_id]:
            raise RuntimeError("PostgreSQL staged duplicate smoke failed")
        if coverage[0]["statement_month"] != "2000-02" or not warnings:
            raise RuntimeError("PostgreSQL staged coverage smoke failed")
        if linkage["was_duplicate"] != 1:
            raise RuntimeError("PostgreSQL import linkage smoke failed")
        return {"references": True, "duplicates": True, "coverage": True, "linkage": True}
    finally:
        with database_transaction(pool) as connection:
            if import_id is not None:
                connection.execute("DELETE FROM import_transactions WHERE import_id=?", (import_id,))
                connection.execute("DELETE FROM import_coverage WHERE import_id=?", (import_id,))
            connection.execute("DELETE FROM merchant_mappings WHERE merchant_normalized=?", (merchant,))
            if transaction_id is not None:
                connection.execute("DELETE FROM transactions WHERE id=?", (transaction_id,))
            if import_id is not None:
                connection.execute("DELETE FROM imports WHERE id=?", (import_id,))
