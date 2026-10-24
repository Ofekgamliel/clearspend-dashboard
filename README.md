# ClearSpend

An offline-first personal finance dashboard backed by a local SQLite database. The dashboard, filters, charts, card breakdown, and statement upload flow now use the imported data rather than demo values.

## Current functionality

- Isracard XLSX recognition and normalization
- MAX XLSX recognition and normalization
- Bank Leumi card PDF parsing
- Apple Numbers conversion helper for macOS
- SQLite import audit log
- Exact-file, semantic-file, and transaction-level duplicate protection
- Preservation of provider-specific fields in the raw source payload
- Dashboard views for the latest month, latest year, and all time
- Historical month selector based on the dates available in imported statements
- Combined and per-card filtering
- Spending metrics, trends, categories, recent transactions, and import insights
- In-dashboard XLSX/PDF upload with duplicate protection
- Three-column income workbook support (`Date`, `Name`, `Amount`) with contributors combined by month
- Collapsible income and all-card remaining-balance summary
- Context-aware monthly averages for all-card spending and amount left
- Persistent merchant category/subcategory mappings that update past transactions and apply to future imports
- Reviewed Hebrew merchant display identities stored separately from transaction categories
- Category transaction views grouped by canonical merchant, with sortable summaries and expandable original transactions
- Billing-month reporting for every dashboard total, chart, card, category, balance, and date filter
- Installment metadata (`current/total`) with MAX billing dates and Isracard statement months
- Installment-safe duplicate detection that keeps equal recurring amounts in separate billing months

Merchant grouping never changes a category. The grouped key is the canonical
merchant identity plus the transaction category, so the same brand can remain
separate in categories such as `אופנה` and `טיסות ותיירות`.

Local financial data is stored under `data/`, which is intentionally excluded from Git.

## Merchant classification priority

Merchant research and import reviews must use this order:

1. Reuse an exact normalized merchant mapping already stored in `merchant_mappings`.
2. Reuse a previously approved alias or an unambiguous merchant-family mapping.
3. Research the merchant online only when the local database has no approved answer.
4. Send ambiguous or contradictory results for manual review without overwriting the database.

An online name match never overrides an exact approved database mapping by itself.

## Reporting month rules

The purchase date is preserved for transaction details, while financial totals use a separate reporting month:

1. Use the provider billing date when supplied (MAX).
2. Otherwise use the imported statement month (Isracard monthly statements).
3. Fall back to the purchase month only when neither is available.

Installment number, installment total, billing date/month, and the reporting-month source are part of transaction identity. This prevents equal installment amounts from being removed as duplicates.

## Profile the samples

```bash
python3 tools/profile_samples.py ../samples --output analysis/sample-profile.json
```

## Import supported samples

Install the PDF dependency into a local virtual environment:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Then import:

```bash
PYTHONPATH=src:. .venv/bin/python tools/import_samples.py ../samples
```

Re-uploading the same files is safe: duplicate uploads and duplicate transactions are recorded but not inserted again.

## Export merchant mappings

Create a JSON snapshot of every normalized merchant, its current category/subcategory, mapping source, cards, and provider-category breakdown:

```bash
PYTHONPATH=src:. .venv/bin/python tools/export_mappings.py
```

The local export is written to `data/merchant-mappings.json`.

## Run the real local dashboard

Do not use `python3 -m http.server`; it can only serve the static prototype. Start the local application server instead:

```bash
PYTHONPATH=src:. .venv/bin/python -m clearspend.server --port 8765
```

Then open [http://localhost:8765](http://localhost:8765). The dashboard reads `data/clearspend.db` and the import dialog sends files only to this local process.

The database, uploaded statements, private analysis, and statement-derived test
fixtures remain local and are intentionally excluded from Git.
