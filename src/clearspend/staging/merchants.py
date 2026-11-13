from __future__ import annotations

import sqlite3
from collections import Counter
from collections.abc import Iterable


def add_staged_merchant_transactions(
    groups: dict[str, dict],
    transactions: Iterable,
    *,
    duplicate_keys: set[str],
    pending_keys: set[str],
) -> None:
    """Accumulate reviewable statement rows by normalized merchant identity."""
    for item in transactions:
        if item.transaction_key in duplicate_keys or item.transaction_key in pending_keys:
            continue
        group = groups.setdefault(item.merchant_normalized, {
            "merchant_normalized": item.merchant_normalized,
            "merchant_raw": item.merchant_raw,
            "transactions": 0,
            "amount": 0.0,
            "providers": set(),
            "cards": set(),
            "first_date": item.transaction_date,
            "last_date": item.transaction_date,
            "provider_categories": Counter(),
        })
        group["transactions"] += 1
        group["amount"] += abs(float(item.charged_amount or 0))
        group["providers"].add(item.provider)
        group["cards"].add(item.card_last4)
        if (
            item.transaction_date
            and (not group["first_date"] or item.transaction_date < group["first_date"])
        ):
            group["first_date"] = item.transaction_date
        if (
            item.transaction_date
            and (not group["last_date"] or item.transaction_date > group["last_date"])
        ):
            group["last_date"] = item.transaction_date
        if item.provider_category:
            group["provider_categories"][item.provider_category] += 1


def resolve_staged_merchants(
    connection: sqlite3.Connection,
    groups: dict[str, dict],
) -> list[dict]:
    """Apply database-first category and display identity suggestions to merchant groups."""
    merchants: list[dict] = []
    for normalized, group in groups.items():
        mapping = connection.execute(
            """SELECT category,subcategory FROM merchant_mappings
            WHERE merchant_normalized=?""",
            (normalized,),
        ).fetchone()
        display = connection.execute(
            """SELECT canonical_group_id,display_name FROM merchant_display_mappings
            WHERE merchant_normalized=?""",
            (normalized,),
        ).fetchone()
        provider_category = (
            group["provider_categories"].most_common(1)[0][0]
            if group["provider_categories"] else None
        )
        match_source = (
            "exact_db" if mapping else "display_alias" if display
            else "provider" if provider_category else "unresolved"
        )
        category = mapping["category"] if mapping else provider_category or "Needs review"
        merchants.append({
            "merchant_normalized": normalized,
            "merchant_raw": group["merchant_raw"],
            "transactions": group["transactions"],
            "amount": round(group["amount"], 2),
            "providers": sorted(group["providers"]),
            "cards": sorted(group["cards"]),
            "first_date": group["first_date"],
            "last_date": group["last_date"],
            "provider_category": provider_category,
            "match_source": match_source,
            "category": category,
            "subcategory": mapping["subcategory"] if mapping else None,
            "display_name": display["display_name"] if display else group["merchant_raw"],
            "canonical_group_id": display["canonical_group_id"] if display else None,
            "needs_review": not bool(mapping),
        })
    merchants.sort(
        key=lambda item: (
            not item["needs_review"], -item["transactions"], item["merchant_raw"]
        )
    )
    return merchants
