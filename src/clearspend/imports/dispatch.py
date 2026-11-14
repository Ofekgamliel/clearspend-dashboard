from __future__ import annotations

from pathlib import Path

from clearspend.imports.domain import ParsedStatement, clean_text
from clearspend.imports.isracard import parse_isracard
from clearspend.imports.leumi import parse_leumi_pdf
from clearspend.imports.max import parse_max
from tools.profile_samples import read_xlsx


def parse_xlsx(path: Path) -> ParsedStatement:
    sheets = read_xlsx(path)
    values = [
        clean_text(value) or ""
        for _, rows in sheets
        for row in rows[:12]
        for value in row.values()
    ]
    joined = " | ".join(values)
    if "תאריך רכישה" in joined and any(
        marker in joined for marker in ("ישראכרט", "פלטינה", "מסטרקארד")
    ):
        return parse_isracard(path, sheets)
    if "4 ספרות אחרונות של כרטיס האשראי" in joined or "-max " in joined.casefold():
        return parse_max(path, sheets)
    raise ValueError("No supported statement profile matched this workbook")


def parse_statement(path: Path) -> ParsedStatement:
    extension = path.suffix.lower()
    if extension == ".xlsx":
        return parse_xlsx(path)
    if extension == ".pdf":
        return parse_leumi_pdf(path)
    raise ValueError(f"Unsupported statement format: {extension}")
