from __future__ import annotations

from pathlib import Path

from clearspend.database.connection import connect_database


def mapping_payload(database: Path) -> dict:
    """Return mapping-review counts, unresolved merchants, and recent import context."""
    connection = connect_database(database)
    try:
        totals = connection.execute(
            """SELECT COUNT(*) merchants,
            SUM(has_uncategorized) needs_review,
            SUM(CASE WHEN has_uncategorized=0 THEN 1 ELSE 0 END) categorized
            FROM (SELECT merchant_normalized,MAX(user_category IS NULL AND provider_category IS NULL) has_uncategorized
                  FROM transactions GROUP BY merchant_normalized)"""
        ).fetchone()
        review = [dict(row) for row in connection.execute(
            """SELECT merchant_raw,merchant_normalized,COUNT(*) transactions,
            ROUND(SUM(ABS(CAST(charged_amount AS REAL))),2) amount
            FROM transactions WHERE user_category IS NULL AND provider_category IS NULL
            GROUP BY merchant_normalized ORDER BY transactions DESC,amount DESC LIMIT 1000"""
        )]
        imports = [dict(row) for row in connection.execute(
            """SELECT id,original_name,provider,card_last4,statement_range,status,
            parsed_rows,inserted_rows,duplicate_rows,imported_at
            FROM imports ORDER BY id DESC LIMIT 8"""
        )]
        for imported in imports:
            imported["coverage"] = [dict(row) for row in connection.execute(
                """SELECT card_last4,statement_month,statement_period,statement_as_of_date,
                purchase_date_from,purchase_date_to,billing_date_from,billing_date_to,
                finalized_rows,pending_rows,outside_cycle_rows,official_total
                FROM import_coverage WHERE import_id=? ORDER BY card_last4""",
                (imported["id"],),
            )]
        mappings = [dict(row) for row in connection.execute(
            """SELECT merchant_normalized,category,subcategory,updated_at
            FROM merchant_mappings ORDER BY updated_at DESC"""
        )]
        categories = [row[0] for row in connection.execute(
            """SELECT DISTINCT category FROM (
                 SELECT user_category category FROM transactions WHERE user_category IS NOT NULL
                 UNION SELECT provider_category category FROM transactions WHERE provider_category IS NOT NULL
               ) WHERE category IS NOT NULL ORDER BY category"""
        )]
        return {
            "summary": dict(totals),
            "review_merchants": review,
            "recent_imports": imports,
            "mappings": mappings,
            "category_suggestions": categories,
        }
    finally:
        connection.close()


def merchants_payload(database: Path) -> dict:
    """Return canonical display identities with their aliases and reviewed recurrence."""
    connection = connect_database(database)
    try:
        aliases = [dict(row) for row in connection.execute(
            """SELECT t.merchant_normalized,
            COALESCE(d.canonical_group_id,t.merchant_normalized) canonical_group_id,
            COALESCE(d.display_name,
              (SELECT recent.merchant_raw FROM transactions recent
               WHERE recent.merchant_normalized=t.merchant_normalized
               ORDER BY recent.transaction_date DESC,recent.id DESC LIMIT 1)) display_name,
            (SELECT recent.merchant_raw FROM transactions recent
             WHERE recent.merchant_normalized=t.merchant_normalized
             ORDER BY recent.transaction_date DESC,recent.id DESC LIMIT 1) merchant_raw,
            COALESCE(m.category,
              (SELECT COALESCE(sample.user_category,sample.provider_category,'Needs review')
               FROM transactions sample WHERE sample.merchant_normalized=t.merchant_normalized
               GROUP BY COALESCE(sample.user_category,sample.provider_category,'Needs review')
               ORDER BY COUNT(*) DESC LIMIT 1),'Needs review') category,
            m.subcategory,COUNT(*) transactions,
            ROUND(SUM(ABS(CAST(t.charged_amount AS REAL))),2) amount,
            MAX(t.transaction_date) last_seen
            FROM transactions t
            LEFT JOIN merchant_display_mappings d ON d.merchant_normalized=t.merchant_normalized
            LEFT JOIN merchant_mappings m ON m.merchant_normalized=t.merchant_normalized
            GROUP BY t.merchant_normalized,d.canonical_group_id,d.display_name,m.category,m.subcategory
            ORDER BY transactions DESC,t.merchant_normalized"""
        )]
        profiles = {
            row["canonical_group_id"]: dict(row) for row in connection.execute(
                """SELECT canonical_group_id,verdict,recurring_type,cadence,cadence_months,
                lifecycle_status,end_month,updated_at FROM recurring_profiles"""
            )
        }
        recurring_members = {
            (row["canonical_group_id"], row["merchant_normalized"]): bool(row["included"])
            for row in connection.execute(
                """SELECT canonical_group_id,merchant_normalized,included
                FROM recurring_profile_members"""
            )
        }
        grouped: dict[str, dict] = {}
        for alias in aliases:
            group_id = alias["canonical_group_id"]
            if group_id not in grouped:
                grouped[group_id] = {
                    "canonical_group_id": group_id,
                    "display_name": alias["display_name"],
                    "transactions": 0,
                    "amount": 0.0,
                    "last_seen": alias["last_seen"],
                    "categories": [],
                    "aliases": [],
                    "recurring_profile": profiles.get(group_id),
                }
            group = grouped[group_id]
            group["transactions"] += int(alias["transactions"])
            group["amount"] = round(group["amount"] + float(alias["amount"] or 0), 2)
            if alias["last_seen"] and (not group["last_seen"] or alias["last_seen"] > group["last_seen"]):
                group["last_seen"] = alias["last_seen"]
            if alias["category"] not in group["categories"]:
                group["categories"].append(alias["category"])
            group["aliases"].append({
                "merchant_normalized": alias["merchant_normalized"],
                "merchant_raw": alias["merchant_raw"],
                "category": alias["category"],
                "subcategory": alias["subcategory"],
                "transactions": int(alias["transactions"]),
                "recurring_included": recurring_members.get(
                    (group_id, alias["merchant_normalized"]), False
                ),
            })
        for group in grouped.values():
            if group["recurring_profile"]:
                group["recurring_profile"]["included_aliases"] = [
                    alias["merchant_normalized"] for alias in group["aliases"]
                    if alias["recurring_included"]
                ]
        merchants = sorted(
            grouped.values(), key=lambda item: (-item["transactions"], item["display_name"])
        )
        categories = [row[0] for row in connection.execute(
            """SELECT DISTINCT category FROM (
                 SELECT category FROM merchant_mappings
                 UNION SELECT user_category category FROM transactions WHERE user_category IS NOT NULL
                 UNION SELECT provider_category category FROM transactions WHERE provider_category IS NOT NULL
               ) WHERE category IS NOT NULL ORDER BY category"""
        )]
        return {
            "summary": {
                "display_identities": len(merchants),
                "mapped_aliases": len(aliases),
                "transactions": sum(item["transactions"] for item in merchants),
                "multiple_categories": sum(len(item["categories"]) > 1 for item in merchants),
                "recurring": sum(
                    item["recurring_profile"] is not None
                    and item["recurring_profile"]["verdict"] == "recurring"
                    for item in merchants
                ),
            },
            "categories": categories,
            "merchants": merchants,
        }
    finally:
        connection.close()
