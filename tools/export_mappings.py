from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


def export_mappings(database_path: Path) -> dict[str, Any]:
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    try:
        manual_mappings = {
            row["merchant_normalized"]: dict(row)
            for row in connection.execute(
                "SELECT merchant_normalized,category,subcategory,updated_at FROM merchant_mappings"
            )
        }
        grouped: dict[str, list[sqlite3.Row]] = defaultdict(list)
        for row in connection.execute(
            """SELECT merchant_normalized,merchant_raw,provider,card_last4,
            provider_category,user_category,user_subcategory
            FROM transactions ORDER BY merchant_normalized,merchant_raw"""
        ):
            grouped[row["merchant_normalized"]].append(row)

        mappings = []
        status_counts: Counter[str] = Counter()
        all_merchants = set(grouped) | set(manual_mappings)
        for normalized in sorted(all_merchants):
            rows = grouped.get(normalized, [])
            manual = manual_mappings.get(normalized)
            provider_counts = Counter(
                row["provider_category"] for row in rows if row["provider_category"]
            )
            uncategorized_count = sum(1 for row in rows if not row["provider_category"])

            if manual:
                category = manual["category"]
                subcategory = manual["subcategory"]
                source = "manual"
                status = "mapped"
            elif len(provider_counts) == 1 and uncategorized_count == 0:
                category = next(iter(provider_counts))
                subcategory = None
                source = "provider"
                status = "mapped"
            elif provider_counts and uncategorized_count:
                category = None
                subcategory = None
                source = "mixed"
                status = "partially_mapped"
            elif len(provider_counts) > 1:
                category = None
                subcategory = None
                source = "provider"
                status = "category_conflict"
            else:
                category = None
                subcategory = None
                source = "none"
                status = "needs_review"

            status_counts[status] += 1
            mappings.append(
                {
                    "merchant_normalized": normalized,
                    "merchant_names": sorted({row["merchant_raw"] for row in rows}),
                    "category": category,
                    "subcategory": subcategory,
                    "mapping_source": source,
                    "status": status,
                    "transaction_count": len(rows),
                    "uncategorized_transaction_count": uncategorized_count,
                    "cards": sorted(
                        {
                            f"{row['provider']}:{row['card_last4']}"
                            for row in rows
                        }
                    ),
                    "provider_category_breakdown": [
                        {"category": name, "transaction_count": count}
                        for name, count in sorted(provider_counts.items())
                    ],
                    "manual_mapping_updated_at": manual["updated_at"] if manual else None,
                }
            )

        return {
            "schema_version": 1,
            "exported_at": datetime.now().astimezone().isoformat(),
            "source_database": database_path.name,
            "merchant_count": len(mappings),
            "status_counts": dict(sorted(status_counts.items())),
            "notes": {
                "category": "Manual mapping when present; otherwise a provider category only when it consistently covers every transaction for the merchant.",
                "subcategory": "Optional and currently populated only by a manual mapping.",
                "null_category": "Review provider_category_breakdown and status before assigning a merchant-wide mapping.",
            },
            "mappings": mappings,
        }
    finally:
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Export the current ClearSpend merchant mappings to JSON")
    parser.add_argument("--database", type=Path, default=Path("data/clearspend.db"))
    parser.add_argument("--output", type=Path, default=Path("data/merchant-mappings.json"))
    args = parser.parse_args()
    payload = export_mappings(args.database.resolve())
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Exported {payload['merchant_count']} merchants to {output}")
    print(json.dumps(payload["status_counts"], ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
