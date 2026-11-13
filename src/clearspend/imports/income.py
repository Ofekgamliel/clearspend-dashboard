from __future__ import annotations

from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from clearspend.imports.domain import IncomeEntry, amount, clean_text
from tools.profile_samples import read_xlsx


def parse_income_month(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    for pattern in (
        "%B %Y",
        "%b %Y",
        "%Y-%m",
        "%Y-%m-%d",
        "%Y-%m-%d %H:%M:%S",
    ):
        try:
            return datetime.strptime(text, pattern).strftime("%Y-%m")
        except ValueError:
            continue
    return None


def parse_income_sheets(
    sheets: list[tuple[str, list[dict[str, Any]]]],
) -> list[IncomeEntry]:
    entries: list[IncomeEntry] = []
    for _sheet_name, rows in sheets:
        header_index = next(
            (
                index
                for index, row in enumerate(rows)
                if clean_text(row.get("A")) in {"תאריכים", "Date", "Dates"}
                and clean_text(row.get("B")) in {"שם", "Name"}
                and clean_text(row.get("C")) in {"סכום", "Amount"}
            ),
            None,
        )
        if header_index is None:
            continue
        counts: Counter[tuple[str, str, str]] = Counter()
        for row in rows[header_index + 1 :]:
            month = parse_income_month(row.get("A"))
            source_name = clean_text(row.get("B"))
            parsed_amount = amount(row.get("C"))
            if not month or not source_name or parsed_amount is None:
                continue
            identity = (month, source_name, parsed_amount)
            counts[identity] += 1
            entry = IncomeEntry(month, source_name, parsed_amount, counts[identity])
            entry.establish_identity()
            entries.append(entry)
    if not entries:
        raise ValueError("Income workbook must contain Date, Name, and Amount columns")
    return entries


def parse_income_xlsx(path: Path) -> list[IncomeEntry]:
    return parse_income_sheets(read_xlsx(path))


def is_income_xlsx(path: Path) -> bool:
    if path.suffix.lower() != ".xlsx":
        return False
    try:
        parse_income_xlsx(path)
        return True
    except ValueError:
        return False
