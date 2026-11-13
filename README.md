# ClearSpend

ClearSpend is a local-first personal finance dashboard for turning credit-card
statements and income records into a private, searchable view of household
spending. The browser UI, Python application server, and SQLite database all run
on the same computer; personal financial data is not stored in this repository.

> ClearSpend is currently a single-user personal project. Its parsers and
> reporting rules are tailored to the statement formats documented below.

## What it does

### Import statements safely

- Parses supported XLSX and PDF statement formats into a common transaction
  model while preserving provider-specific source fields.
- Stages every import for review before changing the live database.
- Reconciles parsed rows with provider totals and separates finalized, pending,
  outside-cycle, duplicate, and unresolved rows.
- Detects exact-file, equivalent-statement, exact-transaction, and possible
  transaction duplicates.
- Records statement provenance and card/date coverage, and creates a database
  backup immediately before an approved import is committed.

### Understand spending

- Month, latest-year, and all-time views with combined or per-card filters.
- Billing-month totals alongside a calendar-day purchase-activity chart.
- Category, card, merchant, installment, recurring-payment, income, and
  amount-left reporting.
- Full-history substring search for transactions; the ordinary unsearched list
  remains capped for responsive browsing.
- Financial observations for monthly exceptions and longer-lasting changes in
  financial routines.

### Add context without rewriting history

- Permanent merchant categories, canonical display names, and one-transaction
  category overrides remain separate decisions.
- Projects and events assign exact transactions to trips or other activities;
  event labels never replace transaction categories.
- Full or partial reimbursements reduce personal spending while preserving the
  original card charge for reconciliation.
- `All spending` and `Routine only` category views separate event spending from
  ordinary habits without changing stored transactions.

## Privacy model

ClearSpend is designed to keep financial state local:

- `data/`, statements, backups, merchant research, and private review files are
  ignored by Git.
- The production frontend requests live values from the local API. Tracked HTML
  and JavaScript must never contain real transactions, income, card suffixes,
  merchants, or statement-derived fixtures.
- A fresh clone contains the application only. Move the SQLite database through
  a separate secure backup process, never through GitHub.

The repository hook and workflow provide guardrails, but reviewing the staged
diff is still required before every commit. See [GIT_WORKFLOW.md](GIT_WORKFLOW.md).

## Quick start

Requirements: Python 3.10 or newer and a local browser.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
PYTHONPATH=src:. .venv/bin/python -m clearspend.server --port 8765
```

Open [http://localhost:8765](http://localhost:8765).

Use the ClearSpend application server—not `python3 -m http.server`. A static
server can render files from `dist/`, but it cannot access SQLite or provide
imports, searches, mappings, events, or other API-backed behavior.

The default database path is `data/clearspend.db`. If it does not exist, the
application initializes an empty local database.

## Supported inputs

- Isracard XLSX statements
- MAX XLSX statements, including separate immediate/foreign transaction sheets
- Bank Leumi card PDF statements
- Income workbooks with `Date`, `Name`, and `Amount` columns; contributors are
  combined into one monthly household total
- Apple Numbers files after local conversion with the macOS helper workflow

Statement formats change over time. Always review recognition, reconciliation,
coverage, pending rows, and the complete insertion preview before approval.
The dashboard does not perform automatic online merchant research during an
import.

## Useful local commands

Run the tracked synthetic suite available in every checkout:

```bash
PYTHONPATH=src:. .venv/bin/python -m unittest discover -s tests/synthetic -v
```

Run the complete local suite when its private statement fixtures are available:

```bash
PYTHONPATH=src:. .venv/bin/python -m unittest discover -s tests -v
```

Run the dependency-free frontend shared-utility tests with Node.js:

```bash
node --test tests/frontend/*.test.js
```

Build the isolated Vue migration preview without changing production `dist/`:

```bash
cd frontend
npm install
npm test
npm run build
```

The preview output is written to ignored `dist-next/`. The current dashboard
continues to run from `dist/` until a reviewed production cutover. With the
local ClearSpend server running, `npm run dev` serves the preview on
`http://127.0.0.1:5173/`; its first read-only feature is the category panel.

Profile local sample statements:

```bash
python3 tools/profile_samples.py ../samples --output analysis/sample-profile.json
```

Export a local merchant-mapping snapshot:

```bash
PYTHONPATH=src:. .venv/bin/python tools/export_mappings.py
```

The export is written to the ignored `data/merchant-mappings.json` path.

## Documentation

- [Architecture and data ownership](docs/ARCHITECTURE.md)
- [Refactoring baseline and current contracts](docs/REFACTORING_BASELINE.md)
- [Database migration design](docs/DATABASE_MIGRATIONS.md)
- [Import and merchant-mapping rules](docs/IMPORT_AND_MAPPING.md)
- [Reporting and calculation rules](docs/REPORTING_RULES.md)
- [Financial observation rules](docs/FINANCIAL_OBSERVATIONS.md)
- [UI and interaction guidelines](docs/UI_GUIDELINES.md)
- [Operations, backups, and recovery](docs/OPERATIONS_AND_RECOVERY.md)
- [Git and privacy workflow](GIT_WORKFLOW.md)
- [Instructions for coding agents](AGENTS.md)
