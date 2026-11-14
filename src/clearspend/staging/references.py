from __future__ import annotations

import sqlite3


def staged_reference_data(connection: sqlite3.Connection) -> tuple[list[str], list[dict]]:
    """Return category and display-identity choices used during staged review."""
    categories = [row[0] for row in connection.execute(
        """SELECT DISTINCT category FROM (
        SELECT category FROM merchant_mappings
        UNION SELECT user_category category FROM transactions WHERE user_category IS NOT NULL
        UNION SELECT provider_category category FROM transactions WHERE provider_category IS NOT NULL
        ) WHERE category IS NOT NULL ORDER BY category"""
    )]
    identities = [dict(row) for row in connection.execute(
        """SELECT d.canonical_group_id,d.display_name,COUNT(DISTINCT d.merchant_normalized) aliases,
        COUNT(t.id) transactions
        FROM merchant_display_mappings d
        LEFT JOIN transactions t ON t.merchant_normalized=d.merchant_normalized
        GROUP BY d.canonical_group_id,d.display_name ORDER BY transactions DESC,d.display_name LIMIT 500"""
    )]
    identities_by_group = {item["canonical_group_id"]: item for item in identities}
    for item in identities:
        item["alias_names"] = []
        item["categories"] = []
        item["category"] = None
        item["category_status"] = "unmapped"
    for row in connection.execute(
        """SELECT canonical_group_id,merchant_normalized
        FROM merchant_display_mappings ORDER BY canonical_group_id,merchant_normalized"""
    ):
        identity = identities_by_group.get(row["canonical_group_id"])
        if identity is not None:
            identity["alias_names"].append(row["merchant_normalized"])
    for row in connection.execute(
        """SELECT d.canonical_group_id,m.category,COUNT(DISTINCT d.merchant_normalized) aliases
        FROM merchant_display_mappings d
        JOIN merchant_mappings m ON m.merchant_normalized=d.merchant_normalized
        GROUP BY d.canonical_group_id,m.category
        ORDER BY d.canonical_group_id,aliases DESC,m.category"""
    ):
        identity = identities_by_group.get(row["canonical_group_id"])
        if identity is not None:
            identity["categories"].append({"category": row["category"], "aliases": row["aliases"]})
    for item in identities:
        if len(item["categories"]) == 1:
            item["category"] = item["categories"][0]["category"]
            item["category_status"] = "unanimous"
        elif len(item["categories"]) > 1:
            item["category_status"] = "mixed"
    return categories, identities
