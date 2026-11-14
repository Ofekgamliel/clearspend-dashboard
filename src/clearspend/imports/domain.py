from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any


INSTALLMENT_NOTE = re.compile(r"תשלום\s+(\d+)\s+מתוך\s+(\d+)")
HEBREW_MONTHS = {
    "ינואר": 1, "פברואר": 2, "מרץ": 3, "אפריל": 4, "מאי": 5, "יוני": 6,
    "יולי": 7, "אוגוסט": 8, "ספטמבר": 9, "אוקטובר": 10, "נובמבר": 11, "דצמבר": 12,
}


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = unicodedata.normalize("NFKC", str(value))
    text = "".join(character for character in text if unicodedata.category(character) != "Cf")
    text = text.replace("\u202a", "").replace("\u202b", "").replace("\u202c", "")
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def normalize_merchant(value: Any) -> str:
    text = clean_text(value) or ""
    text = text.casefold()
    text = re.sub(r"[^\w\u0590-\u05ff]+", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def amount(value: Any) -> str | None:
    if value in (None, ""):
        return None
    try:
        result = Decimal(str(value).replace(",", "").strip())
    except (InvalidOperation, AttributeError):
        return None
    return format(result.quantize(Decimal("0.01")), "f")


def parse_date(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    for pattern in ("%d.%m.%y", "%d-%m-%Y", "%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, pattern).date().isoformat()
        except ValueError:
            continue
    return None


def parse_statement_month(value: Any, filename: str = "") -> str | None:
    """Return YYYY-MM from statement metadata, with filename as a fallback."""
    text = clean_text(value) or ""
    year_match = re.search(r"\b(20\d{2})\b", text)
    if year_match:
        for name, month in HEBREW_MONTHS.items():
            if name in text:
                return f"{year_match.group(1)}-{month:02d}"
        for pattern in ("%B %Y", "%b %Y", "%Y-%m", "%Y-%m-%d"):
            try:
                return datetime.strptime(text, pattern).strftime("%Y-%m")
            except ValueError:
                continue
    filename_match = re.search(r"_(\d{2})_(20\d{2})(?:\D|$)", filename)
    if filename_match and 1 <= int(filename_match.group(1)) <= 12:
        return f"{filename_match.group(2)}-{filename_match.group(1)}"
    dated_filename = re.search(r"(?:^|\D)\d{1,2}[_-](\d{1,2})[_-](20\d{2})(?:\D|$)", filename)
    if dated_filename and 1 <= int(dated_filename.group(1)) <= 12:
        return f"{dated_filename.group(2)}-{int(dated_filename.group(1)):02d}"
    return None


def parse_installment(notes: str | None, transaction_type: str | None = None) -> tuple[int | None, int | None]:
    match = INSTALLMENT_NOTE.search(notes or "")
    if match:
        return int(match.group(1)), int(match.group(2))
    if (transaction_type or "").strip() == "תשלומים":
        return None, None
    return None, None


def transaction_identity(values: dict[str, Any]) -> str:
    identity = {
        "provider": values.get("provider"),
        "card_last4": values.get("card_last4"),
        "transaction_date": values.get("transaction_date"),
        "billing_date": values.get("billing_date"),
        "billing_month": values.get("billing_month"),
        "installment_number": values.get("installment_number"),
        "installment_total": values.get("installment_total"),
        "merchant": values.get("merchant_normalized") or values.get("merchant"),
        "charged_amount": values.get("charged_amount"),
        "charged_currency": values.get("charged_currency"),
        "original_amount": values.get("original_amount"),
        "original_currency": values.get("original_currency"),
    }
    encoded = json.dumps(identity, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


@dataclass
class Transaction:
    provider: str
    card_last4: str
    source_sheet: str
    transaction_date: str | None
    billing_date: str | None
    merchant_raw: str
    merchant_normalized: str
    charged_amount: str | None
    charged_currency: str | None
    original_amount: str | None
    original_currency: str | None
    billing_month: str | None = None
    billing_month_source: str | None = None
    installment_number: int | None = None
    installment_total: int | None = None
    provider_category: str | None = None
    transaction_type: str | None = None
    voucher_number: str | None = None
    notes: str | None = None
    execution_method: str | None = None
    exchange_rate: str | None = None
    source_payload: dict[str, Any] | None = None
    occurrence: int = 1
    base_key: str = ""
    transaction_key: str = ""

    def establish_identity(self) -> None:
        self.base_key = transaction_identity(asdict(self))
        self.transaction_key = hashlib.sha256(f"{self.base_key}:{self.occurrence}".encode()).hexdigest()


@dataclass
class ParsedStatement:
    provider: str
    card_last4: str
    product_name: str | None
    date_range: str | None
    transactions: list[Transaction]
    official_total: str | None = None
    statement_as_of_date: str | None = None

    @property
    def semantic_hash(self) -> str:
        keys = sorted(transaction.transaction_key for transaction in self.transactions)
        payload = json.dumps(
            {"provider": self.provider, "card_last4": self.card_last4, "transactions": keys},
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode()).hexdigest()


@dataclass
class IncomeEntry:
    month: str
    source_name: str
    amount: str
    occurrence: int = 1
    entry_key: str = ""

    def establish_identity(self) -> None:
        payload = json.dumps(
            {"month": self.month, "source_name": self.source_name, "amount": self.amount},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        base_key = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        self.entry_key = hashlib.sha256(f"{base_key}:{self.occurrence}".encode()).hexdigest()


def assign_occurrences(transactions: list[Transaction]) -> None:
    counts: Counter[str] = Counter()
    for transaction in transactions:
        transaction.occurrence = 1
        transaction.establish_identity()
        counts[transaction.base_key] += 1
        transaction.occurrence = counts[transaction.base_key]
        transaction.establish_identity()
