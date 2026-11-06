# ClearSpend architecture

This document is the source of truth for ClearSpend's application boundaries,
runtime components, local data ownership, and persistence model.

## Core principle

ClearSpend is an offline-first, local application. The browser renders the UI,
the local Python server performs application operations, and SQLite stores the
user's financial state. GitHub stores application code only.

No production frontend file may contain real transactions, merchants, amounts,
income, dates, card suffixes, or other statement-derived information.

## Runtime flow

```text
Browser
  -> dist/index.html, dist/styles.css, dist/app.js
  -> local /api requests
Python server
  -> parsing, validation, dashboard queries, mappings, imports
SQLite database
  -> local transactions, mappings, income, and import audit history
```

The real application must be started with:

```bash
PYTHONPATH=src:. .venv/bin/python -m clearspend.server --port 8765
```

`python3 -m http.server` serves static files only. It cannot provide database
data, imports, mapping changes, or other API-backed behavior.

## Source layout

- `dist/` contains the production browser application.
- `src/clearspend/server.py` serves static assets and implements the local API.
- `src/clearspend/import_engine.py` parses statements, owns the SQLite schema,
  imports normalized records, and applies duplicate protection.
- `tools/` contains generic local utilities permitted by `.gitignore`.
- `data/` contains the live database and user-specific exports. It is private.
- `analysis/`, `samples/`, private tests, and review prototypes remain local.

## Local API responsibilities

The server currently exposes operations for:

- Health and dashboard summaries
- Transactions and categories
- Merchant mappings and merchant management
- Transaction-specific category corrections
- Transaction-specific full or partial reimbursement adjustments
- Reviewed recurring profiles, merchant-level add/remove decisions, lifecycle,
  cadence, and installment summaries
- Import analysis and approved import commits

The frontend must obtain user data through these local APIs. Do not generate a
tracked HTML or JavaScript snapshot containing live database results.

## Persistence model

The principal SQLite tables have separate responsibilities:

- `imports`: statement import audit records and file/semantic fingerprints.
- `transactions`: normalized source transactions and provider-specific fields.
- `merchant_mappings`: permanent category rules keyed by normalized merchant.
- `merchant_display_mappings`: canonical display identities without replacing
  the original statement description.
- `transaction_category_overrides`: exceptions applying to one transaction.
- `transaction_spending_adjustments`: reviewed full or partial reimbursements
  keyed to one transaction; the imported card charge remains unchanged.
- `import_transactions`: links imports to inserted or duplicate transactions.
- `income_imports`: income-file import audit records.
- `income_entries`: monthly income contributions used in aggregate calculations.
- `recurring_profiles`: reviewed recurring/not-recurring decisions and editable
  cadence/lifecycle state keyed by canonical display identity.
- `recurring_profile_members`: the exact normalized merchant aliases included
  in or excluded from each recurring profile. A shared display identity does
  not automatically make every underlying alias recurring.
- `observation_reviews`: reversible reviewed decisions for an exact duplicate
  group, recurring billing occurrence, or unusual transaction. Structured
  transaction and recurring-series references keep one decision from
  suppressing a different future finding.

Do not merge these concepts. In particular, display identity, merchant category,
and transaction-specific category are intentionally independent.

## Data ownership and portability

The application repository is portable; the user's financial state is not part
of Git. A fresh clone starts without personal transactions. Move or restore the
database through a separate approved backup process.

The default database is `data/clearspend.db`. Uploaded statements, database
backups, mappings, and research artifacts must remain in ignored local paths.

## Database-change requirements

Before a schema migration, bulk mapping update, category rewrite, duplicate
repair, or other material mutation:

1. Create and verify a database backup.
2. Record relevant before-counts and totals.
3. Prefer one transaction so failures can roll back cleanly.
4. Make migrations safe to re-run where practical.
5. Verify counts, totals, mappings, and representative records afterward.
6. Preserve original provider data and reviewed user decisions.

Never silently rebuild or replace the live database. Never delete private local
data merely to make the repository appear clean.
