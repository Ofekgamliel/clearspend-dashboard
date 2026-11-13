from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from clearspend.imports.domain import (
    ParsedStatement,
    Transaction,
    amount,
    assign_occurrences,
    clean_text,
    normalize_merchant,
    parse_date,
    parse_installment,
)


MAX_DATE = re.compile(r"^\d{2}-\d{2}-\d{4}$")


def parse_max(
    path: Path,
    sheets: list[tuple[str, list[dict[str, Any]]]],
) -> ParsedStatement:
    data_sheets = [(name, rows) for name, rows in sheets if name != "Export Summary"]
    if not data_sheets:
        raise ValueError("MAX workbook has no transaction sheets")
    metadata = clean_text(data_sheets[0][1][1].get("A")) or ""
    match = re.match(r"(\d{4})-(.+)", metadata)
    is_multi_card_export = metadata.startswith("כל הכרטיסים")
    if not match and not is_multi_card_export:
        raise ValueError("Could not find MAX card suffix")
    if match:
        card_last4, product = match.groups()
    else:
        card_last4, product = "multiple", metadata
    date_range = clean_text(data_sheets[0][1][2].get("A"))
    primary_rows = next(
        (rows for name, rows in data_sheets if name == "עסקאות במועד החיוב"),
        data_sheets[0][1],
    )
    official_total = None
    for index, row in enumerate(primary_rows):
        if clean_text(row.get("A")) != "סך הכל":
            continue
        for total_row in primary_rows[index : index + 3]:
            for value in total_row.values():
                text = clean_text(value) or ""
                match_total = re.search(r"-?[\d,]+(?:\.\d+)?", text)
                if match_total:
                    official_total = amount(match_total.group(0))
                    break
            if official_total is not None:
                break
        if official_total is not None:
            break
    transactions: list[Transaction] = []
    for sheet_name, rows in data_sheets:
        for row in rows:
            first = clean_text(row.get("A")) or ""
            if not MAX_DATE.match(first):
                continue
            merchant = clean_text(row.get("B"))
            if not merchant:
                continue
            transaction_card = card_last4
            if is_multi_card_export:
                raw_card = clean_text(row.get("D")) or ""
                card_match = re.search(r"(\d{1,4})(?:\.0)?$", raw_card)
                if not card_match:
                    raise ValueError(
                        f"Could not find MAX card suffix for transaction row in {sheet_name}"
                    )
                transaction_card = card_match.group(1).zfill(4)
            transaction_date = parse_date(first)
            billing_date = parse_date(row.get("J"))
            transaction_type = clean_text(row.get("E"))
            notes = clean_text(row.get("K"))
            source_sheet = (
                f"{sheet_name}:immediate"
                if "מיידי" in (transaction_type or "")
                else sheet_name
            )
            installment_number, installment_total = parse_installment(
                notes,
                transaction_type,
            )
            payload = {
                key: value for key, value in row.items() if value not in (None, "")
            }
            transactions.append(
                Transaction(
                    provider="max",
                    card_last4=transaction_card,
                    source_sheet=source_sheet,
                    transaction_date=transaction_date,
                    billing_date=billing_date,
                    merchant_raw=merchant,
                    merchant_normalized=normalize_merchant(merchant),
                    charged_amount=amount(row.get("F")),
                    charged_currency=clean_text(row.get("G")),
                    original_amount=amount(row.get("H")),
                    original_currency=clean_text(row.get("I")),
                    billing_month=(billing_date or transaction_date or "")[:7] or None,
                    billing_month_source=(
                        "provider" if billing_date else "purchase_date"
                    ),
                    installment_number=installment_number,
                    installment_total=installment_total,
                    provider_category=clean_text(row.get("C")),
                    transaction_type=transaction_type,
                    notes=notes,
                    execution_method=clean_text(row.get("O")),
                    exchange_rate=clean_text(row.get("P")),
                    source_payload=payload,
                )
            )
    assign_occurrences(transactions)
    return ParsedStatement(
        "max",
        card_last4,
        product.strip(),
        date_range,
        transactions,
        official_total=official_total,
    )
