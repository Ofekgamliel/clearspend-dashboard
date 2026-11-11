from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import unicodedata
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable

from tools.profile_samples import read_xlsx, sha256_path


ISRAELI_DATE = re.compile(r"^\d{2}\.\d{2}\.\d{2}$")
MAX_DATE = re.compile(r"^\d{2}-\d{2}-\d{4}$")
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


def parse_income_month(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    for pattern in ("%B %Y", "%b %Y", "%Y-%m", "%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, pattern).strftime("%Y-%m")
        except ValueError:
            continue
    return None


def parse_income_sheets(sheets: list[tuple[str, list[dict[str, Any]]]]) -> list[IncomeEntry]:
    entries: list[IncomeEntry] = []
    for _sheet_name, rows in sheets:
        header_index = next((
            index for index, row in enumerate(rows)
            if clean_text(row.get("A")) in {"תאריכים", "Date", "Dates"}
            and clean_text(row.get("B")) in {"שם", "Name"}
            and clean_text(row.get("C")) in {"סכום", "Amount"}
        ), None)
        if header_index is None:
            continue
        counts: Counter[tuple[str, str, str]] = Counter()
        for row in rows[header_index + 1:]:
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


def assign_occurrences(transactions: list[Transaction]) -> None:
    counts: Counter[str] = Counter()
    for transaction in transactions:
        transaction.occurrence = 1
        transaction.establish_identity()
        counts[transaction.base_key] += 1
        transaction.occurrence = counts[transaction.base_key]
        transaction.establish_identity()


def parse_isracard(path: Path, sheets: list[tuple[str, list[dict[str, Any]]]]) -> ParsedStatement:
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
        row_text = " ".join(filter(None, (clean_text(value) for value in row.values())))
        as_of_match = re.search(r"נכונים לתאריך\s*(\d{2}/\d{2}/\d{4})", row_text)
        if as_of_match:
            statement_as_of_date = datetime.strptime(as_of_match.group(1), "%d/%m/%Y").date().isoformat()
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
        payload = {key: value for key, value in row.items() if value not in (None, "")}
        transaction = Transaction(
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
            billing_month=statement_month if uses_statement_month else (transaction_date or "")[:7] or None,
            billing_month_source="statement" if uses_statement_month else "purchase_date",
            installment_number=installment_number,
            installment_total=installment_total,
            voucher_number=clean_text(row.get("G")),
            notes=notes,
            source_payload=payload,
        )
        transactions.append(transaction)
    assign_occurrences(transactions)
    return ParsedStatement("isracard", card_last4, product, statement_label, transactions,
                           official_total=official_total,
                           statement_as_of_date=statement_as_of_date)


def parse_max(path: Path, sheets: list[tuple[str, list[dict[str, Any]]]]) -> ParsedStatement:
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
        for total_row in primary_rows[index:index + 3]:
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
                    raise ValueError(f"Could not find MAX card suffix for transaction row in {sheet_name}")
                transaction_card = card_match.group(1).zfill(4)
            transaction_date = parse_date(first)
            billing_date = parse_date(row.get("J"))
            transaction_type = clean_text(row.get("E"))
            notes = clean_text(row.get("K"))
            source_sheet = (
                f"{sheet_name}:immediate"
                if "מיידי" in (transaction_type or "") else sheet_name
            )
            installment_number, installment_total = parse_installment(notes, transaction_type)
            payload = {key: value for key, value in row.items() if value not in (None, "")}
            transaction = Transaction(
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
                billing_month_source="provider" if billing_date else "purchase_date",
                installment_number=installment_number,
                installment_total=installment_total,
                provider_category=clean_text(row.get("C")),
                transaction_type=transaction_type,
                notes=notes,
                execution_method=clean_text(row.get("O")),
                exchange_rate=clean_text(row.get("P")),
                source_payload=payload,
            )
            transactions.append(transaction)
    assign_occurrences(transactions)
    return ParsedStatement(
        "max", card_last4, product.strip(), date_range, transactions,
        official_total=official_total,
    )


def parse_xlsx(path: Path) -> ParsedStatement:
    sheets = read_xlsx(path)
    values = [clean_text(value) or "" for _, rows in sheets for row in rows[:12] for value in row.values()]
    joined = " | ".join(values)
    if "תאריך רכישה" in joined and any(
        marker in joined for marker in ("ישראכרט", "פלטינה", "מסטרקארד")
    ):
        return parse_isracard(path, sheets)
    if "4 ספרות אחרונות של כרטיס האשראי" in joined or "-max " in joined.casefold():
        return parse_max(path, sheets)
    raise ValueError("No supported statement profile matched this workbook")


def parse_leumi_pdf(path: Path) -> ParsedStatement:
    try:
        from pypdf import PdfReader
    except ImportError as error:
        raise RuntimeError("PDF support requires the pypdf package") from error
    text = "\n".join((page.extract_text() or "") for page in PdfReader(path).pages)
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
        transaction = Transaction(
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
            billing_month=statement_month or (transaction_date or "")[:7] or None,
            billing_month_source="statement" if statement_month else "purchase_date",
            transaction_type="עסקה רגילה",
            notes=f"time {time_text}" if time_text else None,
            source_payload={"line": line},
        )
        transactions.append(transaction)
    if not transactions:
        raise ValueError("No transaction rows were parsed from the Bank Leumi PDF")
    assign_occurrences(transactions)
    return ParsedStatement("isracard", card_last4, "לאומי מסטרקארד", statement_range, transactions)


def parse_statement(path: Path) -> ParsedStatement:
    extension = path.suffix.lower()
    if extension == ".xlsx":
        return parse_xlsx(path)
    if extension == ".pdf":
        return parse_leumi_pdf(path)
    raise ValueError(f"Unsupported statement format: {extension}")


SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS imports (
  id INTEGER PRIMARY KEY,
  original_name TEXT NOT NULL,
  source_path TEXT NOT NULL,
  byte_hash TEXT NOT NULL,
  semantic_hash TEXT,
  source_format TEXT NOT NULL,
  provider TEXT,
  card_last4 TEXT,
  product_name TEXT,
  statement_range TEXT,
  status TEXT NOT NULL,
  parsed_rows INTEGER NOT NULL DEFAULT 0,
  inserted_rows INTEGER NOT NULL DEFAULT 0,
  duplicate_rows INTEGER NOT NULL DEFAULT 0,
  imported_at TEXT NOT NULL,
  error_message TEXT
);
CREATE INDEX IF NOT EXISTS idx_imports_byte_hash ON imports(byte_hash);
CREATE INDEX IF NOT EXISTS idx_imports_semantic_hash ON imports(semantic_hash);
CREATE TABLE IF NOT EXISTS transactions (
  id INTEGER PRIMARY KEY,
  transaction_key TEXT NOT NULL UNIQUE,
  base_key TEXT NOT NULL,
  occurrence INTEGER NOT NULL,
  provider TEXT NOT NULL,
  card_last4 TEXT NOT NULL,
  source_sheet TEXT NOT NULL,
  transaction_date TEXT,
  billing_date TEXT,
  billing_month TEXT,
  billing_month_source TEXT,
  installment_number INTEGER,
  installment_total INTEGER,
  merchant_raw TEXT NOT NULL,
  merchant_normalized TEXT NOT NULL,
  charged_amount TEXT,
  charged_currency TEXT,
  original_amount TEXT,
  original_currency TEXT,
  provider_category TEXT,
  user_category TEXT,
  user_subcategory TEXT,
  transaction_type TEXT,
  voucher_number TEXT,
  notes TEXT,
  execution_method TEXT,
  exchange_rate TEXT,
  source_payload TEXT,
  first_import_id INTEGER NOT NULL REFERENCES imports(id),
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_transactions_card_date ON transactions(card_last4, transaction_date);
CREATE INDEX IF NOT EXISTS idx_transactions_merchant ON transactions(merchant_normalized);
CREATE TABLE IF NOT EXISTS merchant_mappings (
  merchant_normalized TEXT PRIMARY KEY,
  category TEXT NOT NULL,
  subcategory TEXT,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS merchant_display_mappings (
  merchant_normalized TEXT PRIMARY KEY,
  canonical_group_id TEXT NOT NULL,
  display_name TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_merchant_display_group ON merchant_display_mappings(canonical_group_id);
CREATE TABLE IF NOT EXISTS transaction_category_overrides (
  transaction_id INTEGER PRIMARY KEY REFERENCES transactions(id) ON DELETE CASCADE,
  category TEXT NOT NULL,
  subcategory TEXT,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS transaction_spending_adjustments (
  transaction_id INTEGER PRIMARY KEY REFERENCES transactions(id) ON DELETE CASCADE,
  adjustment_type TEXT NOT NULL CHECK(adjustment_type IN ('full_reimbursement','partial_reimbursement')),
  reimbursed_amount TEXT NOT NULL,
  reimbursement_date TEXT,
  note TEXT,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS import_transactions (
  import_id INTEGER NOT NULL REFERENCES imports(id),
  transaction_id INTEGER NOT NULL REFERENCES transactions(id),
  was_duplicate INTEGER NOT NULL,
  PRIMARY KEY(import_id, transaction_id)
);
CREATE TABLE IF NOT EXISTS import_coverage (
  import_id INTEGER NOT NULL REFERENCES imports(id) ON DELETE CASCADE,
  card_last4 TEXT NOT NULL,
  statement_month TEXT,
  statement_period TEXT,
  statement_as_of_date TEXT,
  purchase_date_from TEXT,
  purchase_date_to TEXT,
  billing_date_from TEXT,
  billing_date_to TEXT,
  finalized_rows INTEGER NOT NULL DEFAULT 0,
  pending_rows INTEGER NOT NULL DEFAULT 0,
  outside_cycle_rows INTEGER NOT NULL DEFAULT 0,
  official_total TEXT,
  PRIMARY KEY(import_id,card_last4)
);
CREATE INDEX IF NOT EXISTS idx_import_coverage_card_month
  ON import_coverage(card_last4,statement_month);
CREATE TABLE IF NOT EXISTS income_imports (
  id INTEGER PRIMARY KEY,
  original_name TEXT NOT NULL,
  source_path TEXT NOT NULL,
  byte_hash TEXT NOT NULL,
  source_format TEXT NOT NULL,
  status TEXT NOT NULL,
  parsed_rows INTEGER NOT NULL DEFAULT 0,
  inserted_rows INTEGER NOT NULL DEFAULT 0,
  duplicate_rows INTEGER NOT NULL DEFAULT 0,
  imported_at TEXT NOT NULL,
  error_message TEXT
);
CREATE INDEX IF NOT EXISTS idx_income_imports_byte_hash ON income_imports(byte_hash);
CREATE TABLE IF NOT EXISTS income_entries (
  id INTEGER PRIMARY KEY,
  month TEXT NOT NULL,
  source_name TEXT NOT NULL,
  amount TEXT NOT NULL,
  entry_key TEXT NOT NULL UNIQUE,
  first_import_id INTEGER NOT NULL REFERENCES income_imports(id),
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_income_entries_month ON income_entries(month);
CREATE TABLE IF NOT EXISTS recurring_profiles (
  canonical_group_id TEXT PRIMARY KEY,
  display_name TEXT NOT NULL,
  verdict TEXT NOT NULL CHECK(verdict IN ('recurring','not_recurring')),
  recurring_type TEXT,
  cadence TEXT,
  cadence_months INTEGER,
  lifecycle_status TEXT NOT NULL DEFAULT 'active'
    CHECK(lifecycle_status IN ('active','ended','paused','unknown')),
  end_month TEXT,
  review_count INTEGER NOT NULL DEFAULT 1,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS recurring_profile_members (
  canonical_group_id TEXT NOT NULL REFERENCES recurring_profiles(canonical_group_id) ON DELETE CASCADE,
  merchant_normalized TEXT NOT NULL,
  included INTEGER NOT NULL DEFAULT 1 CHECK(included IN (0,1)),
  updated_at TEXT NOT NULL,
  PRIMARY KEY(canonical_group_id,merchant_normalized)
);
CREATE INDEX IF NOT EXISTS idx_recurring_members_merchant
  ON recurring_profile_members(merchant_normalized,included);
CREATE TABLE IF NOT EXISTS observation_reviews (
  finding_key TEXT PRIMARY KEY,
  observation_type TEXT NOT NULL,
  resolution TEXT NOT NULL,
  month TEXT NOT NULL,
  transaction_ids TEXT NOT NULL DEFAULT '[]',
  recurring_series_id TEXT,
  occurrence_start TEXT,
  occurrence_end TEXT,
  merchant_label TEXT,
  active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
  reviewed_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_observation_reviews_active
  ON observation_reviews(active,observation_type,month);
CREATE TABLE IF NOT EXISTS events (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  event_type TEXT NOT NULL DEFAULT 'trip',
  destination TEXT,
  icon TEXT,
  start_date TEXT NOT NULL,
  end_date TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'completed'
    CHECK(status IN ('planned','active','completed','cancelled')),
  budget TEXT,
  notes TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  CHECK(end_date >= start_date)
);
CREATE TABLE IF NOT EXISTS event_transactions (
  transaction_id INTEGER PRIMARY KEY REFERENCES transactions(id) ON DELETE CASCADE,
  event_id TEXT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  assigned_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_event_transactions_event
  ON event_transactions(event_id,transaction_id);
"""


class ImportDatabase:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(SCHEMA)
        transaction_columns = {
            row["name"] for row in self.connection.execute("PRAGMA table_info(transactions)")
        }
        recurring_columns = {
            row["name"] for row in self.connection.execute("PRAGMA table_info(recurring_profiles)")
        }
        event_columns = {
            row["name"] for row in self.connection.execute("PRAGMA table_info(events)")
        }
        if "destination" not in event_columns:
            self.connection.execute("ALTER TABLE events ADD COLUMN destination TEXT")
        if "review_count" not in recurring_columns:
            self.connection.execute(
                "ALTER TABLE recurring_profiles ADD COLUMN review_count INTEGER NOT NULL DEFAULT 1"
            )
        self.connection.execute(
            """INSERT OR IGNORE INTO recurring_profile_members(
            canonical_group_id,merchant_normalized,included,updated_at
            )
            SELECT p.canonical_group_id,t.merchant_normalized,
              CASE WHEN p.verdict='recurring' THEN 1 ELSE 0 END,p.updated_at
            FROM recurring_profiles p
            JOIN transactions t
            LEFT JOIN merchant_display_mappings d
              ON d.merchant_normalized=t.merchant_normalized
            WHERE COALESCE(d.canonical_group_id,t.merchant_normalized)=p.canonical_group_id
            GROUP BY p.canonical_group_id,t.merchant_normalized"""
        )
        reporting_columns_added = False
        for column, definition in (
            ("billing_month", "TEXT"),
            ("billing_month_source", "TEXT"),
            ("installment_number", "INTEGER"),
            ("installment_total", "INTEGER"),
        ):
            if column not in transaction_columns:
                self.connection.execute(f"ALTER TABLE transactions ADD COLUMN {column} {definition}")
                reporting_columns_added = True
        if "user_category" not in transaction_columns:
            self.connection.execute("ALTER TABLE transactions ADD COLUMN user_category TEXT")
        if "user_subcategory" not in transaction_columns:
            self.connection.execute("ALTER TABLE transactions ADD COLUMN user_subcategory TEXT")
        self.connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_transactions_billing_month ON transactions(billing_month)"
        )
        self._backfill_reporting_fields(rekey=reporting_columns_added)
        self._backfill_import_coverage()
        self.connection.executescript(
            """CREATE TRIGGER IF NOT EXISTS apply_merchant_mapping_after_insert
            AFTER INSERT ON transactions
            WHEN EXISTS (SELECT 1 FROM merchant_mappings WHERE merchant_normalized=NEW.merchant_normalized)
            BEGIN
              UPDATE transactions SET
                user_category=(SELECT category FROM merchant_mappings WHERE merchant_normalized=NEW.merchant_normalized),
                user_subcategory=(SELECT subcategory FROM merchant_mappings WHERE merchant_normalized=NEW.merchant_normalized)
              WHERE id=NEW.id;
            END;"""
        )
        self.connection.commit()

    def _backfill_import_coverage(self) -> None:
        rows = self.connection.execute(
            """SELECT i.id,i.statement_range,t.card_last4,
            MIN(t.transaction_date) purchase_date_from,MAX(t.transaction_date) purchase_date_to,
            MIN(t.billing_date) billing_date_from,MAX(t.billing_date) billing_date_to,
            COUNT(DISTINCT t.id) finalized_rows
            FROM imports i JOIN import_transactions it ON it.import_id=i.id
            JOIN transactions t ON t.id=it.transaction_id
            WHERE i.status='imported' GROUP BY i.id,t.card_last4"""
        ).fetchall()
        for row in rows:
            statement_month = parse_statement_month(row["statement_range"])
            self.connection.execute(
                """INSERT OR IGNORE INTO import_coverage(
                import_id,card_last4,statement_month,statement_period,purchase_date_from,
                purchase_date_to,billing_date_from,billing_date_to,finalized_rows
                ) VALUES(?,?,?,?,?,?,?,?,?)""",
                (row["id"], row["card_last4"], statement_month, row["statement_range"],
                 row["purchase_date_from"], row["purchase_date_to"], row["billing_date_from"],
                 row["billing_date_to"], row["finalized_rows"]),
            )

    def _backfill_reporting_fields(self, rekey: bool = False) -> None:
        import_rows = {
            row["id"]: row
            for row in self.connection.execute(
                "SELECT id,original_name,statement_range FROM imports"
            )
        }
        rows = self.connection.execute("SELECT * FROM transactions ORDER BY id").fetchall()
        keyed_rows: list[tuple[int, str, int]] = []
        occurrences: Counter[str] = Counter()
        for row in rows:
            imported = import_rows.get(row["first_import_id"])
            statement_month = parse_statement_month(
                imported["statement_range"] if imported else None,
                imported["original_name"] if imported else "",
            )
            if row["billing_date"]:
                billing_month = row["billing_date"][:7]
                source = "provider"
            elif row["provider"] == "isracard" and row["source_sheet"].endswith(":monthly") and statement_month:
                billing_month = statement_month
                source = "statement"
            elif row["source_sheet"] == "Bank Leumi PDF" and statement_month:
                billing_month = statement_month
                source = "statement"
            else:
                billing_month = (row["transaction_date"] or "")[:7] or None
                source = "purchase_date"
            installment_number, installment_total = parse_installment(row["notes"], row["transaction_type"])
            self.connection.execute(
                """UPDATE transactions SET billing_month=?,billing_month_source=?,
                installment_number=?,installment_total=? WHERE id=?""",
                (billing_month, source, installment_number, installment_total, row["id"]),
            )
            if rekey:
                identity_values = dict(row)
                identity_values.update({
                    "billing_month": billing_month,
                    "billing_month_source": source,
                    "installment_number": installment_number,
                    "installment_total": installment_total,
                })
                base_key = transaction_identity(identity_values)
                occurrences[base_key] += 1
                keyed_rows.append((row["id"], base_key, occurrences[base_key]))
        if rekey and keyed_rows:
            for transaction_id, _, _ in keyed_rows:
                self.connection.execute(
                    "UPDATE transactions SET transaction_key=?,base_key=? WHERE id=?",
                    (f"reporting-migration-{transaction_id}", f"reporting-migration-{transaction_id}", transaction_id),
                )
            for transaction_id, base_key, occurrence in keyed_rows:
                transaction_key = hashlib.sha256(f"{base_key}:{occurrence}".encode()).hexdigest()
                self.connection.execute(
                    """UPDATE transactions SET transaction_key=?,base_key=?,occurrence=? WHERE id=?""",
                    (transaction_key, base_key, occurrence, transaction_id),
                )

    def close(self) -> None:
        self.connection.close()

    def import_statement(self, path: Path, probable_duplicate_matches: dict[str, int] | None = None,
                         excluded_transaction_keys: set[str] | None = None) -> dict[str, Any]:
        probable_duplicate_matches = probable_duplicate_matches or {}
        excluded_transaction_keys = excluded_transaction_keys or set()
        byte_hash = sha256_path(path)
        source_format = path.suffix.lower()
        prior_file = self.connection.execute(
            "SELECT * FROM imports WHERE byte_hash = ? AND status IN ('imported', 'duplicate_file') ORDER BY id LIMIT 1",
            (byte_hash,),
        ).fetchone()
        now = datetime.now().astimezone().isoformat()
        if prior_file:
            cursor = self.connection.execute(
                """INSERT INTO imports(original_name,source_path,byte_hash,source_format,status,imported_at,
                provider,card_last4,parsed_rows,inserted_rows,duplicate_rows)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (path.name, str(path), byte_hash, source_format, "duplicate_file", now,
                 prior_file["provider"], prior_file["card_last4"], prior_file["parsed_rows"], 0, prior_file["parsed_rows"]),
            )
            self.connection.commit()
            return {"import_id": cursor.lastrowid, "status": "duplicate_file", "matches_import_id": prior_file["id"]}

        try:
            statement = parse_statement(path)
        except Exception as error:
            cursor = self.connection.execute(
                """INSERT INTO imports(original_name,source_path,byte_hash,source_format,status,imported_at,error_message)
                VALUES(?,?,?,?,?,?,?)""",
                (path.name, str(path), byte_hash, source_format, "failed", now, str(error)),
            )
            self.connection.commit()
            return {"import_id": cursor.lastrowid, "status": "failed", "error": str(error)}

        semantic_hash = statement.semantic_hash
        prior_semantic = self.connection.execute(
            "SELECT id FROM imports WHERE semantic_hash = ? AND status IN ('imported', 'duplicate_content') ORDER BY id LIMIT 1",
            (semantic_hash,),
        ).fetchone()
        status = "duplicate_content" if prior_semantic else "imported"
        cursor = self.connection.execute(
            """INSERT INTO imports(original_name,source_path,byte_hash,semantic_hash,source_format,provider,card_last4,
            product_name,statement_range,status,parsed_rows,imported_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (path.name, str(path), byte_hash, semantic_hash, source_format, statement.provider, statement.card_last4,
             statement.product_name, statement.date_range, status, len(statement.transactions), now),
        )
        import_id = cursor.lastrowid
        inserted = 0
        duplicates = 0
        reviewed_duplicates = 0
        for transaction in statement.transactions:
            if transaction.transaction_key in excluded_transaction_keys:
                continue
            voucher_exact_id = None
            if transaction.voucher_number:
                voucher_exact = self.connection.execute(
                    """SELECT id FROM transactions WHERE provider=? AND card_last4=?
                    AND voucher_number=? AND base_key=? ORDER BY id LIMIT 1""",
                    (transaction.provider, transaction.card_last4,
                     transaction.voucher_number, transaction.base_key),
                ).fetchone()
                voucher_exact_id = voucher_exact["id"] if voucher_exact else None
            if voucher_exact_id is not None:
                self.connection.execute(
                    "INSERT OR IGNORE INTO import_transactions(import_id,transaction_id,was_duplicate) VALUES(?,?,1)",
                    (import_id, voucher_exact_id),
                )
                duplicates += 1
                continue
            reviewed_match_id = probable_duplicate_matches.get(transaction.transaction_key)
            if reviewed_match_id is not None:
                matched = self.connection.execute(
                    "SELECT id FROM transactions WHERE id=?", (reviewed_match_id,)
                ).fetchone()
                if not matched:
                    raise ValueError(f"Reviewed duplicate transaction {reviewed_match_id} no longer exists")
                self.connection.execute(
                    "INSERT OR IGNORE INTO import_transactions(import_id,transaction_id,was_duplicate) VALUES(?,?,1)",
                    (import_id, reviewed_match_id),
                )
                duplicates += 1
                reviewed_duplicates += 1
                continue
            key_collision = self.connection.execute(
                "SELECT id,voucher_number FROM transactions WHERE transaction_key=?",
                (transaction.transaction_key,),
            ).fetchone()
            if (key_collision and transaction.voucher_number and key_collision["voucher_number"]
                    and transaction.voucher_number != key_collision["voucher_number"]):
                max_occurrence = self.connection.execute(
                    "SELECT COALESCE(MAX(occurrence),0) FROM transactions WHERE base_key=?",
                    (transaction.base_key,),
                ).fetchone()[0]
                transaction.occurrence = int(max_occurrence) + 1
                transaction.transaction_key = hashlib.sha256(
                    f"{transaction.base_key}:{transaction.occurrence}".encode()
                ).hexdigest()
            fields = asdict(transaction)
            payload = json.dumps(fields.pop("source_payload"), ensure_ascii=False, sort_keys=True)
            columns = list(fields) + ["source_payload", "first_import_id", "created_at"]
            values = list(fields.values()) + [payload, import_id, now]
            placeholders = ",".join("?" for _ in columns)
            try:
                transaction_cursor = self.connection.execute(
                    f"INSERT INTO transactions({','.join(columns)}) VALUES({placeholders})", values
                )
                transaction_id = transaction_cursor.lastrowid
                was_duplicate = 0
                inserted += 1
            except sqlite3.IntegrityError:
                transaction_id = self.connection.execute(
                    "SELECT id FROM transactions WHERE transaction_key = ?", (transaction.transaction_key,)
                ).fetchone()["id"]
                was_duplicate = 1
                duplicates += 1
            self.connection.execute(
                "INSERT OR IGNORE INTO import_transactions(import_id,transaction_id,was_duplicate) VALUES(?,?,?)",
                (import_id, transaction_id, was_duplicate),
            )
        self.connection.execute(
            "UPDATE imports SET inserted_rows=?, duplicate_rows=? WHERE id=?", (inserted, duplicates, import_id)
        )
        self.connection.commit()
        return {
            "import_id": import_id,
            "status": status,
            "provider": statement.provider,
            "card_last4": statement.card_last4,
            "parsed": len(statement.transactions),
            "inserted": inserted,
            "duplicates": duplicates,
            "reviewed_duplicates": reviewed_duplicates,
            "matches_import_id": prior_semantic["id"] if prior_semantic else None,
        }

    def import_income(self, path: Path) -> dict[str, Any]:
        if path.suffix.lower() != ".xlsx":
            raise ValueError("Income files must use XLSX format")
        byte_hash = sha256_path(path)
        now = datetime.now().astimezone().isoformat()
        prior_file = self.connection.execute(
            "SELECT id,parsed_rows FROM income_imports WHERE byte_hash=? AND status IN ('imported','duplicate_file') ORDER BY id LIMIT 1",
            (byte_hash,),
        ).fetchone()
        if prior_file:
            cursor = self.connection.execute(
                """INSERT INTO income_imports(original_name,source_path,byte_hash,source_format,status,
                parsed_rows,inserted_rows,duplicate_rows,imported_at) VALUES(?,?,?,?,?,?,?,?,?)""",
                (path.name, str(path), byte_hash, ".xlsx", "duplicate_file", prior_file["parsed_rows"], 0,
                 prior_file["parsed_rows"], now),
            )
            self.connection.commit()
            return {"import_id": cursor.lastrowid, "status": "duplicate_file", "kind": "income",
                    "matches_import_id": prior_file["id"]}
        try:
            entries = parse_income_xlsx(path)
        except Exception as error:
            cursor = self.connection.execute(
                """INSERT INTO income_imports(original_name,source_path,byte_hash,source_format,status,
                imported_at,error_message) VALUES(?,?,?,?,?,?,?)""",
                (path.name, str(path), byte_hash, ".xlsx", "failed", now, str(error)),
            )
            self.connection.commit()
            return {"import_id": cursor.lastrowid, "status": "failed", "kind": "income", "error": str(error)}
        cursor = self.connection.execute(
            """INSERT INTO income_imports(original_name,source_path,byte_hash,source_format,status,
            parsed_rows,imported_at) VALUES(?,?,?,?,?,?,?)""",
            (path.name, str(path), byte_hash, ".xlsx", "imported", len(entries), now),
        )
        import_id = cursor.lastrowid
        inserted = duplicates = 0
        for entry in entries:
            try:
                self.connection.execute(
                    """INSERT INTO income_entries(month,source_name,amount,entry_key,first_import_id,created_at)
                    VALUES(?,?,?,?,?,?)""",
                    (entry.month, entry.source_name, entry.amount, entry.entry_key, import_id, now),
                )
                inserted += 1
            except sqlite3.IntegrityError:
                duplicates += 1
        status = "duplicate_content" if inserted == 0 else "imported"
        self.connection.execute(
            "UPDATE income_imports SET status=?,inserted_rows=?,duplicate_rows=? WHERE id=?",
            (status, inserted, duplicates, import_id),
        )
        self.connection.commit()
        return {"import_id": import_id, "status": status, "kind": "income", "parsed": len(entries),
                "inserted": inserted, "duplicates": duplicates}

    def import_file(self, path: Path, probable_duplicate_matches: dict[str, int] | None = None,
                    excluded_transaction_keys: set[str] | None = None) -> dict[str, Any]:
        return self.import_income(path) if is_income_xlsx(path) else self.import_statement(
            path, probable_duplicate_matches=probable_duplicate_matches,
            excluded_transaction_keys=excluded_transaction_keys,
        )

    def summary(self) -> dict[str, Any]:
        imports = self.connection.execute(
            "SELECT status, COUNT(*) AS count FROM imports GROUP BY status ORDER BY status"
        ).fetchall()
        cards = self.connection.execute(
            """SELECT provider, card_last4, COUNT(*) AS transactions,
            MIN(transaction_date) AS first_date, MAX(transaction_date) AS last_date
            FROM transactions GROUP BY provider, card_last4 ORDER BY provider, card_last4"""
        ).fetchall()
        return {"imports": [dict(row) for row in imports], "cards": [dict(row) for row in cards]}


def import_paths(database: Path, paths: Iterable[Path]) -> dict[str, Any]:
    db = ImportDatabase(database)
    try:
        results = [db.import_file(path) for path in paths]
        return {"results": results, "summary": db.summary()}
    finally:
        db.close()
