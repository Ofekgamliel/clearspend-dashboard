from __future__ import annotations

import re
from pathlib import Path

from clearspend.imports.domain import (
    ParsedStatement,
    Transaction,
    amount,
    assign_occurrences,
    clean_text,
    normalize_merchant,
    parse_date,
    parse_statement_month,
)


def parse_leumi_text(path: Path, text: str) -> ParsedStatement:
    """Parse extracted Bank Leumi statement text into canonical transactions."""
    normalized_text = clean_text(text) or ""
    card_match = re.search(r"(\d{4})\s+לאומי מסטרקארד", normalized_text)
    if not card_match:
        raise ValueError("Could not find a supported Bank Leumi card suffix")
    card_last4 = card_match.group(1)
    range_match = re.search(r"(\d{4}\s+\S+)\s+לתקופה", normalized_text)
    statement_range = range_match.group(1) if range_match else None
    statement_month = parse_statement_month(statement_range, path.name)
    transactions: list[Transaction] = []
    line_pattern = re.compile(r"^(\d{2}[/.]\d{2}[/.]\d{2})(\d{2}:\d{2})?(.*)$")
    trailing_amount = re.compile(r"(-?[\d,]+\.\d{2})\s*$")
    for raw_line in text.splitlines():
        line = clean_text(raw_line) or ""
        match = line_pattern.match(line)
        if not match or "עסקה רגילה" not in match.group(3):
            continue
        date_text, time_text, body = match.groups()
        before_type, after_type = body.split("עסקה רגילה", 1)
        charged_match = re.match(r"\s*(-?[\d,]+\.\d{2})", after_type)
        original_match = trailing_amount.search(before_type)
        if original_match:
            merchant = clean_text(before_type[: original_match.start()])
            original_value = amount(original_match.group(1))
        else:
            merchant = clean_text(before_type)
            original_value = amount(charged_match.group(1)) if charged_match else None
        if not merchant or not charged_match:
            continue
        charged_value = amount(charged_match.group(1))
        transaction_date = parse_date(date_text.replace("/", "."))
        transactions.append(
            Transaction(
                provider="isracard",
                card_last4=card_last4,
                source_sheet="Bank Leumi PDF",
                transaction_date=transaction_date,
                billing_date=None,
                merchant_raw=merchant,
                merchant_normalized=normalize_merchant(merchant),
                charged_amount=charged_value,
                charged_currency="₪",
                original_amount=original_value,
                original_currency="₪",
                billing_month=(
                    statement_month or (transaction_date or "")[:7] or None
                ),
                billing_month_source=(
                    "statement" if statement_month else "purchase_date"
                ),
                transaction_type="עסקה רגילה",
                notes=f"time {time_text}" if time_text else None,
                source_payload={"line": line},
            )
        )
    if not transactions:
        raise ValueError("No transaction rows were parsed from the Bank Leumi PDF")
    assign_occurrences(transactions)
    return ParsedStatement(
        "isracard",
        card_last4,
        "לאומי מסטרקארד",
        statement_range,
        transactions,
    )


def parse_leumi_pdf(path: Path) -> ParsedStatement:
    try:
        from pypdf import PdfReader
    except ImportError as error:
        raise RuntimeError("PDF support requires the pypdf package") from error
    text = "\n".join((page.extract_text() or "") for page in PdfReader(path).pages)
    return parse_leumi_text(path, text)
