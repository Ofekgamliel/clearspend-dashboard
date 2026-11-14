"""The current ClearSpend SQLite schema, without migration side effects."""

BASE_SCHEMA_SQL = """
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


BILLING_MONTH_INDEX_SQL = (
    "CREATE INDEX IF NOT EXISTS idx_transactions_billing_month "
    "ON transactions(billing_month)"
)

MERCHANT_MAPPING_TRIGGER_SQL = """CREATE TRIGGER IF NOT EXISTS apply_merchant_mapping_after_insert
AFTER INSERT ON transactions
WHEN EXISTS (
  SELECT 1 FROM merchant_mappings
  WHERE merchant_normalized=NEW.merchant_normalized
)
BEGIN
  UPDATE transactions SET
    user_category=(
      SELECT category FROM merchant_mappings
      WHERE merchant_normalized=NEW.merchant_normalized
    ),
    user_subcategory=(
      SELECT subcategory FROM merchant_mappings
      WHERE merchant_normalized=NEW.merchant_normalized
    )
  WHERE id=NEW.id;
END;"""
