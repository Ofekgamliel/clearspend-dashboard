from __future__ import annotations

import hashlib
import sqlite3
import re


def merchant_decision_map(decisions: list[dict]) -> dict[str, dict]:
    return {
        str(item.get("merchant_normalized", "")): item
        for item in decisions
        if str(item.get("merchant_normalized", ""))
    }


def merchants_requiring_review(analysis: dict) -> set[str]:
    return {
        str(item.get("merchant_normalized", ""))
        for item in analysis.get("merchants", [])
        if item.get("needs_review") and str(item.get("merchant_normalized", ""))
    }


def reviewed_duplicate_matches(
    analysis: dict,
    duplicate_decisions: list[dict],
) -> dict[int, dict[str, int]]:
    """Validate all possible-duplicate decisions and return approved existing matches by file."""
    possible_by_id = {
        item["candidate_id"]: item for item in analysis.get("possible_duplicates", [])
    }
    duplicate_action_map = {
        str(item.get("candidate_id", "")): str(item.get("action", ""))
        for item in duplicate_decisions
    }
    missing_duplicate_decisions = set(possible_by_id) - set(duplicate_action_map)
    invalid_duplicate_decisions = {
        candidate_id for candidate_id, action in duplicate_action_map.items()
        if candidate_id not in possible_by_id or action not in {"skip", "import"}
    }
    if missing_duplicate_decisions:
        raise ValueError("Every possible duplicate must be reviewed before import")
    if invalid_duplicate_decisions:
        raise ValueError("A possible-duplicate decision is invalid or no longer current")
    reviewed_matches_by_file: dict[int, dict[str, int]] = {}
    for candidate_id, action in duplicate_action_map.items():
        if action != "skip":
            continue
        candidate = possible_by_id[candidate_id]
        matched_ids = candidate.get("matched_transaction_ids", [])
        if not matched_ids:
            raise ValueError("A reviewed duplicate has no matching existing transaction")
        reviewed_matches_by_file.setdefault(int(candidate["file_index"]), {})[
            candidate["transaction_key"]
        ] = int(matched_ids[0])
    return reviewed_matches_by_file


def apply_permanent_merchant_decisions(
    connection: sqlite3.Connection,
    decisions: dict[str, dict],
    now: str,
) -> None:
    """Persist exact-name category and display decisions selected during review."""
    for normalized, decision in decisions.items():
        resolution = str(decision.get("resolution", "needs_review"))
        scope = str(decision.get("scope", "exact"))
        category = str(decision.get("category", "")).strip()
        display_name = str(decision.get("display_name", "")).strip()
        requested_group_id = str(decision.get("canonical_group_id", "")).strip()
        if resolution == "link" and (scope != "exact" or not requested_group_id):
            raise ValueError(
                f"Linking {normalized} to an existing merchant requires a selected identity "
                "and the permanent exact-name scope"
            )
        if resolution not in {"needs_review", "exclude"} and category and scope == "exact":
            connection.execute(
                """INSERT INTO merchant_mappings(merchant_normalized,category,subcategory,updated_at)
                VALUES(?,?,NULL,?) ON CONFLICT(merchant_normalized) DO UPDATE SET
                category=excluded.category,updated_at=excluded.updated_at""",
                (normalized, category, now),
            )
        if resolution not in {"needs_review", "exclude"} and display_name and scope == "exact":
            group_id = requested_group_id
            if not group_id:
                display_key = re.sub(r"\s+", " ", display_name.casefold()).strip()
                group_id = "custom:" + hashlib.sha256(display_key.encode("utf-8")).hexdigest()[:20]
            connection.execute(
                """INSERT INTO merchant_display_mappings(
                merchant_normalized,canonical_group_id,display_name,updated_at
                ) VALUES(?,?,?,?) ON CONFLICT(merchant_normalized) DO UPDATE SET
                canonical_group_id=excluded.canonical_group_id,
                display_name=excluded.display_name,updated_at=excluded.updated_at""",
                (normalized, group_id, display_name, now),
            )


def apply_imported_transaction_decisions(
    connection: sqlite3.Connection,
    import_id: int,
    decisions: dict[str, dict],
    review_required_merchants: set[str],
    now: str,
) -> int:
    """Apply exclusions and batch-only category outcomes to newly inserted rows."""
    excluded = 0
    new_rows = connection.execute(
        """SELECT t.id,t.merchant_normalized FROM transactions t
        JOIN import_transactions it ON it.transaction_id=t.id
        WHERE it.import_id=? AND it.was_duplicate=0""",
        (import_id,),
    ).fetchall()
    for row in new_rows:
        decision = decisions.get(row["merchant_normalized"], {})
        resolution = str(decision.get("resolution", "needs_review"))
        scope = str(decision.get("scope", "exact"))
        category = str(decision.get("category", "")).strip()
        if resolution == "exclude":
            connection.execute(
                "DELETE FROM import_transactions WHERE import_id=? AND transaction_id=?",
                (import_id, row["id"]),
            )
            connection.execute("DELETE FROM transactions WHERE id=?", (row["id"],))
            excluded += 1
        elif (
            resolution == "needs_review"
            and row["merchant_normalized"] in review_required_merchants
        ) or (scope == "batch" and category):
            override_category = "Needs review" if resolution == "needs_review" else category
            connection.execute(
                """INSERT INTO transaction_category_overrides(
                transaction_id,category,subcategory,updated_at
                ) VALUES(?,?,NULL,?) ON CONFLICT(transaction_id) DO UPDATE SET
                category=excluded.category,updated_at=excluded.updated_at""",
                (row["id"], override_category, now),
            )
    return excluded
