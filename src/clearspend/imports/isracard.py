from __future__ import annotations

import re
from datetime import datetime
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
    parse_statement_month,
)


ISRAELI_DATE = re.compile(r"^\d{2}\.\d{2}\.\d{2}$")


def parse_isracard(
    path: Path,
    sheets: list[tuple[str, list[dict[str, Any]]]],
) -> ParsedStatement:
    name, rows = sheets[0]
    metadata = clean_text(rows[1].get("A")) or ""
    match = re.search(r"(\d{4})\s*$", metadata)
    if not match:
        raise ValueError("Could not find Isracard card suffix")
    card_last4 = match.group(1)
    product = re.sub(r"\s*-\s*\d{4}\s*$", "", metadata).strip()
    statement_label = clean_text(rows[0].get("C"))
    statement_month = parse_statement_month(statement_label, path.name)
    official_total = None
    statement_as_of_date = None
    for row in rows:
        label = clean_text(row.get("B")) or ""
        if "סה\"כ לחיוב החודש בכרטיס" in label:
            official_total = amount(row.get("E"))
        row_text = " ".join(
            filter(None, (clean_text(value) for value in row.values()))
        )
        as_of_match = re.search(r"נכונים לתאריך\s*(\d{2}/\d{2}/\d{4})", row_text)
        if as_of_match:
            statement_as_of_date = datetime.strptime(
                as_of_match.group(1),
                "%d/%m/%Y",
            ).date().isoformat()
    transactions: list[Transaction] = []
    section = "monthly"
    for row in rows:
        first = clean_text(row.get("A")) or ""
        if first == "עסקאות בחיוב מחוץ למועד":
            section = "immediate"
            continue
        if not ISRAELI_DATE.match(first):
            continue
        merchant = clean_text(row.get("B"))
        if not merchant:
            continue
        transaction_date = parse_date(first)
        notes = clean_text(row.get("H"))
        installment_number, installment_total = parse_installment(notes)
        uses_statement_month = section == "monthly" and statement_month is not None
        payload = {
            key: value for key, value in row.items() if value not in (None, "")
        }
        transactions.append(
            Transaction(
                provider="isracard",
                card_last4=card_last4,
                source_sheet=f"{name}:{section}",
                transaction_date=transaction_date,
                billing_date=None,
                merchant_raw=merchant,
                merchant_normalized=normalize_merchant(merchant),
                charged_amount=amount(row.get("E")),
                charged_currency=clean_text(row.get("F")),
                original_amount=amount(row.get("C")),
                original_currency=clean_text(row.get("D")),
                billing_month=(
                    statement_month
                    if uses_statement_month
                    else (transaction_date or "")[:7] or None
                ),
                billing_month_source=(
                    "statement" if uses_statement_month else "purchase_date"
                ),
                installment_number=installment_number,
                installment_total=installment_total,
                voucher_number=clean_text(row.get("G")),
                notes=notes,
                source_payload=payload,
            )
        )
    assign_occurrences(transactions)
    return ParsedStatement(
        "isracard",
        card_last4,
        product,
        statement_label,
        transactions,
        official_total=official_total,
        statement_as_of_date=statement_as_of_date,
    )
