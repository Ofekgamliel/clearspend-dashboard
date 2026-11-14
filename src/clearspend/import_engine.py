from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

# Compatibility exports for existing callers. New code should import these from
# clearspend.imports directly.
from clearspend.imports.dispatch import parse_statement, parse_xlsx
from clearspend.imports.domain import (
    IncomeEntry,
    ParsedStatement,
    Transaction,
    amount,
    assign_occurrences,
    clean_text,
    normalize_merchant,
    parse_date,
    parse_installment,
    parse_statement_month,
    transaction_identity,
)
from clearspend.imports.income import (
    is_income_xlsx,
    parse_income_month,
    parse_income_sheets,
    parse_income_xlsx,
)
from clearspend.imports.isracard import parse_isracard
from clearspend.imports.leumi import parse_leumi_pdf
from clearspend.imports.max import parse_max
from clearspend.imports.repository import ImportDatabase


def import_paths(database: Path, paths: Iterable[Path]) -> dict[str, Any]:
    db = ImportDatabase(database)
    try:
        results = [db.import_file(path) for path in paths]
        return {"results": results, "summary": db.summary()}
    finally:
        db.close()
