from __future__ import annotations

from datetime import datetime
from pathlib import Path

from clearspend.database.connection import connect_database


def save_mapping(database: Path, merchant: str, category: str, subcategory: str) -> dict:
    """Persist a merchant-wide category rule and update its existing transactions."""
    merchant = merchant.strip()
    category = category.strip()
    subcategory = subcategory.strip()
    if not merchant or not category:
        raise ValueError("Merchant and category are required")
    connection = connect_database(database)
    try:
        now = datetime.now().astimezone().isoformat()
        connection.execute(
            """INSERT INTO merchant_mappings(merchant_normalized,category,subcategory,updated_at)
            VALUES(?,?,?,?) ON CONFLICT(merchant_normalized) DO UPDATE SET
            category=excluded.category,subcategory=excluded.subcategory,updated_at=excluded.updated_at""",
            (merchant, category, subcategory or None, now),
        )
        cursor = connection.execute(
            "UPDATE transactions SET user_category=?,user_subcategory=? WHERE merchant_normalized=?",
            (category, subcategory or None, merchant),
        )
        connection.commit()
        return {
            "status": "saved",
            "merchant_normalized": merchant,
            "category": category,
            "subcategory": subcategory or None,
            "transactions_updated": cursor.rowcount,
        }
    finally:
        connection.close()


def save_merchant(database: Path, group_id: str, display_name: str, aliases: list[dict]) -> dict:
    """Update a display identity and any explicitly edited alias category rules."""
    group_id = group_id.strip()
    display_name = display_name.strip()
    if not group_id or not display_name:
        raise ValueError("Merchant group and display name are required")
    connection = connect_database(database)
    try:
        existing = [row[0] for row in connection.execute(
            """SELECT DISTINCT t.merchant_normalized FROM transactions t
            LEFT JOIN merchant_display_mappings d ON d.merchant_normalized=t.merchant_normalized
            WHERE COALESCE(d.canonical_group_id,t.merchant_normalized)=?""",
            (group_id,),
        )]
        if not existing:
            raise ValueError("Merchant group was not found")
        allowed = set(existing)
        requested = {str(item.get("merchant_normalized", "")).strip(): item for item in aliases}
        if any(merchant not in allowed for merchant in requested):
            raise ValueError("A merchant alias does not belong to this group")
        now = datetime.now().astimezone().isoformat()
        for merchant in existing:
            connection.execute(
                """INSERT INTO merchant_display_mappings(
                merchant_normalized,canonical_group_id,display_name,updated_at
                ) VALUES(?,?,?,?) ON CONFLICT(merchant_normalized) DO UPDATE SET
                canonical_group_id=excluded.canonical_group_id,
                display_name=excluded.display_name,updated_at=excluded.updated_at""",
                (merchant, group_id, display_name, now),
            )
        transactions_updated = 0
        category_rules_updated = 0
        for merchant, item in requested.items():
            category = str(item.get("category", "")).strip()
            subcategory = str(item.get("subcategory", "")).strip()
            if not category:
                raise ValueError("Every edited alias needs a category")
            connection.execute(
                """INSERT INTO merchant_mappings(merchant_normalized,category,subcategory,updated_at)
                VALUES(?,?,?,?) ON CONFLICT(merchant_normalized) DO UPDATE SET
                category=excluded.category,subcategory=excluded.subcategory,updated_at=excluded.updated_at""",
                (merchant, category, subcategory or None, now),
            )
            cursor = connection.execute(
                "UPDATE transactions SET user_category=?,user_subcategory=? WHERE merchant_normalized=?",
                (category, subcategory or None, merchant),
            )
            transactions_updated += cursor.rowcount
            category_rules_updated += 1
        connection.commit()
        return {
            "status": "saved",
            "display_name": display_name,
            "aliases_updated": len(existing),
            "category_rules_updated": category_rules_updated,
            "transactions_updated": transactions_updated,
        }
    finally:
        connection.close()
