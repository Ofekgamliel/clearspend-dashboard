# ClearSpend

ClearSpend is a locally run personal finance dashboard for turning credit-card
statements and income records into a private, searchable view of household
spending. Its Vue 3 + TypeScript + Vite frontend and Python application server
run on the same computer; authoritative financial state is stored in a private
Supabase PostgreSQL database and is never stored in this repository.

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

ClearSpend keeps its browser and Python server local while storing its
authoritative financial state in a private Supabase PostgreSQL database:

- `data/`, statements, backups, merchant research, and private review files are
  ignored by Git.
- The production frontend requests live values from the local API. Tracked HTML
  and JavaScript must never contain real transactions, income, card suffixes,
  merchants, or statement-derived fixtures.
- PostgreSQL connection metadata stays in an ignored local configuration file.
  Database and archive passwords stay in macOS Keychain and never in Git.
- A fresh clone contains the application only. Restore access through the
  approved runtime configuration, certificate, Keychain items, and encrypted
  PostgreSQL backups—never through GitHub.

The repository hook and workflow provide guardrails, but reviewing the staged
diff is still required before every commit. See [GIT_WORKFLOW.md](GIT_WORKFLOW.md).

## Quick start

Requirements: Python 3.10 or newer and a local browser.

An existing installation also needs its ignored runtime configuration, trusted
CA certificate, and macOS Keychain entries. A fresh clone can start from the
sanitized [`config/postgresql-runtime.example.json`](config/postgresql-runtime.example.json)
and [`config/postgresql-admin.example.json`](config/postgresql-admin.example.json)
templates; neither file contains a password or real project identifier. See
[`docs/OPERATIONS_AND_RECOVERY.md`](docs/OPERATIONS_AND_RECOVERY.md) for the
separate existing-project and replacement-environment procedures.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
PYTHONPATH=src:. .venv/bin/python -m clearspend.server \
  --postgresql-config data/postgresql-runtime.json \
  --port 8765
```

Open [http://localhost:8765](http://localhost:8765). Before troubleshooting dashboard data, verify
`http://localhost:8765/api/health` returns `status: ok` and the expected API
compatibility identifier.

The Python process keeps the code from the branch where it was started. After
switching between `main` and a refactor branch, stop it with `Ctrl-C` and start
it again from the new branch. The frontend blocks data requests and shows a
retryable restart message when it detects an incompatible stale server.

Use the ClearSpend application server—not `python3 -m http.server`. A static
server can render files from `dist/`, but it cannot access the database or provide
imports, searches, mappings, events, or other API-backed behavior.

PostgreSQL is the authoritative runtime database. The server requires the
ignored runtime configuration shown above and fails closed if it
cannot connect or verify the schema. Starting without an explicit database
selection fails. Archival inspection must deliberately use
`--legacy-sqlite-database data/clearspend.db`; that mode is not for normal use
or an automatic fallback.

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

Install the test-only Python dependencies before running the complete test and
browser suites:

```bash
.venv/bin/python -m pip install -r requirements-dev.txt
```

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

Build the Vue production frontend:

```bash
cd frontend
npm ci
npm test
npm run typecheck
npm run build
npx playwright install chromium
npm run test:e2e
```

The build writes generated assets to `dist/`, which is served by the local
ClearSpend application. With the Python server running, `npm run dev` provides
an optional development server at `http://127.0.0.1:5173/` and proxies local
API requests to port 8765.

The Playwright suite creates and replaces only its dedicated synthetic database
in the operating system's temporary directory. It starts the real local server
on port 8785 and never opens `data/clearspend.db`.

Tracked visual baselines are reviewed with `npm run test:e2e` on macOS. GitHub
CI runs the same browser workflows with `npm run test:e2e:ci`, omitting only
pixel comparisons because Chromium text rendering differs across operating
systems.

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

- [Documentation map and ownership](docs/README.md)
- [Architecture and module boundaries](docs/ARCHITECTURE.md)
- [Local API contracts](docs/API_CONTRACTS.md)
- [Testing and change acceptance](docs/TESTING.md)
- [Database migrations](docs/DATABASE_MIGRATIONS.md)
- [Import and merchant-mapping rules](docs/IMPORT_AND_MAPPING.md)
- [Reporting and calculation rules](docs/REPORTING_RULES.md)
- [Financial observation rules](docs/FINANCIAL_OBSERVATIONS.md)
- [UI and interaction guidelines](docs/UI_GUIDELINES.md)
- [Operations, backups, and recovery](docs/OPERATIONS_AND_RECOVERY.md)
- [Git and privacy workflow](GIT_WORKFLOW.md)
- [Instructions for coding agents](AGENTS.md)

Completed refactoring plans and parity checklists are retained under
[`docs/archive/`](docs/archive/) as historical records, not current sources of
truth.
