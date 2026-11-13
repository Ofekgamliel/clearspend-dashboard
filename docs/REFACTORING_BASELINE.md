# Refactoring baseline

This document records the current ClearSpend runtime contracts before code is
moved between modules. It is an inventory, not a proposed final architecture.
All examples and tests associated with this baseline must use synthetic data.

## Runtime entry points

- Application: `python -m clearspend.server`
- Default bind address: `127.0.0.1`
- Default port: `8765`
- Production frontend source: `dist/`
- Default private database: `data/clearspend.db`
- HTTP implementation: `BaseHTTPRequestHandler` and `ThreadingHTTPServer`
- Upload implementation: bounded standard-library multipart decoding in
  `http/multipart.py`; the removed `cgi` module is no longer a Python 3.13 blocker

The server serves static files and JSON APIs from one local process. Unknown
static paths fall back to `dist/index.html`.

## HTTP API inventory

The table records the current routes that must remain compatible while the
backend is separated. Successful JSON responses use `Cache-Control: no-store`.
Most validation failures return `400` with `{"error": "..."}` and unexpected
failures return the same shape with `500`.

### Read operations

| Method and path | Inputs | Current owner | Primary consumer |
| --- | --- | --- | --- |
| `GET /api/health` | None | HTTP handler | Manual health check |
| `GET /api/dashboard` | `period`, `card`, `month` | `dashboard_payload` | Main dashboard |
| `GET /api/transactions` | `period`, `card`, `month`, `q`, `category`, `event_scope` | `transactions_payload` | Recent/all/category transactions and search |
| `GET /api/categories` | `period`, `card`, `month`, `event_scope` | `categories_payload` | Category panel and details |
| `GET /api/mapping` | None | `mapping_payload` | Mapping editor and import history |
| `GET /api/merchants` | None | `merchants_payload` | Merchant management and import reference data |
| `GET /api/recurring` | `period`, `card`, `month` | `recurring_payload` | Recurring panel, modal and observations |
| `GET /api/events` | `period`, `card`, `month` | `events_payload` | Projects and events |
| `GET /api/observation-reviews` | None | `observation_reviews_payload` | Observation suppression/resolution state |

Valid `period` values are `month`, `year` and `all`. Valid `event_scope`
values are `all` and `routine`.

### Write operations

| Method and path | Purpose | Primary persistent effects |
| --- | --- | --- |
| `POST /api/mapping` | Save one permanent merchant category rule | `merchant_mappings`; historical transaction category fields |
| `POST /api/merchants` | Save display identity and reviewed alias categories | `merchant_display_mappings`, `merchant_mappings`; historical transaction category fields |
| `POST /api/transaction-category` | Correct one transaction only | `transaction_category_overrides` |
| `POST /api/transaction-adjustment` | Add, change or remove a reimbursement | `transaction_spending_adjustments` |
| `POST /api/transaction-event` | Assign or unassign one transaction | `event_transactions` |
| `POST /api/events` | Create an event | `events` |
| `POST /api/event-settings` | Edit event identity and presentation settings | `events` |
| `POST /api/recurring-profile` | Edit cadence and lifecycle | `recurring_profiles` |
| `POST /api/recurring-profile/manage` | Add/remove a reviewed recurring decision and aliases | `recurring_profiles`, `recurring_profile_members` |
| `POST /api/observation-review` | Save or undo a review resolution | `observation_reviews` |
| `POST /api/import/analyze` | Parse and stage uploaded files | Temporary files and in-memory batch only; no live transaction commit |
| `POST /api/import/commit` | Reanalyze and commit an approved staged batch | Backup plus imports, transactions, mappings, coverage and related audit rows |
| `POST /api/import` | Legacy immediate import | Direct import without the production staged-review UI |

The production frontend calls `import/analyze` followed by `import/commit`. The
legacy direct-import route conflicts with the current rule that imports must be
staged and reviewed. Keep it unchanged during baseline capture, add contract
coverage, then deprecate or remove it as a separately reviewed behavior change.

## Core response contracts used by the frontend

These are compatibility boundaries, not complete JSON schemas.

### Dashboard

The dashboard response includes:

- `period`, `selected_card`, `available_months`
- `metrics`
- `income_summary`, including averages
- `cards`, `categories`, `category_comparison`
- `recent_transactions`
- `trend`, `trend_mode`, `purchase_activity_summary`
- `insights`, `latest_import`

### Transactions

The transactions response includes the selected period/card/scope, sortable
transaction rows, category/display identity, original provider evidence,
personal-spending adjustments and event assignment data. Search is performed
by the backend and therefore is not limited to the first rows rendered by the
browser.

### Recurring and events

Recurring responses contain reviewed recurring series, installment
commitments, history, lifecycle/cadence metadata and burden metrics. Event
responses contain visible events/groups and exact transaction membership.
Event dates control period visibility; membership is stored separately.

## SQLite schema inventory

| Table | Responsibility |
| --- | --- |
| `imports` | Statement import audit and file/semantic fingerprints |
| `transactions` | Canonical provider transaction records |
| `merchant_mappings` | Permanent category rules per normalized merchant |
| `merchant_display_mappings` | Canonical display groups and labels |
| `transaction_category_overrides` | Category exception for one transaction |
| `transaction_spending_adjustments` | Reviewed reimbursement for one transaction |
| `import_transactions` | Import-to-transaction audit links |
| `import_coverage` | Per-card statement coverage and reconciliation evidence |
| `income_imports` | Income import audit |
| `income_entries` | Monthly income contributions |
| `recurring_profiles` | Reviewed recurring verdict and lifecycle/cadence |
| `recurring_profile_members` | Exact aliases included in a recurring profile |
| `observation_reviews` | Reversible finding resolutions |
| `events` | Project/event identity and display settings |
| `event_transactions` | Exact transaction-to-event membership |

Current indexes support import fingerprints, card/date and merchant transaction
lookup, display groups, import coverage, income month, recurring member lookup,
observation review lookup and event membership. The current trigger
`apply_merchant_mapping_after_insert` copies an existing reviewed merchant
category into a newly inserted transaction.

Fresh databases now receive an explicit schema version through the migration
runner. Compatible existing unversioned databases remain readable without an
implicit migration; their approved cutover uses the separate migration command
and a verified backup. `ImportDatabase.__init__` no longer performs inline
`ALTER TABLE`, backfill or re-key operations.

## Current write boundaries

1. Explicit migration execution can change schema after creating a verified
   backup; ordinary database opening only creates a schema when the file is new.
2. Statement and income import methods create audit records and insert data.
3. Staged commit additionally saves reviewed merchant/display decisions,
   possible-duplicate decisions and coverage data.
4. Merchant management can update both rules and historical denormalized
   transaction category fields.
5. Transaction category, reimbursement and event membership are intentionally
   transaction-specific writes.
6. Recurring management and observation review use separate reviewed-state
   tables.

These concepts must remain independent during repository extraction.

## Calculation ownership baseline

| Concern | Current authority | Target authority |
| --- | --- | --- |
| Ordinary application SQLite connection defaults | `database/connection.py` | `database/connection.py` |
| Canonical transaction/statement/income models, normalization and identity | `imports/domain.py` | `imports/domain.py` |
| Income workbook recognition and parsing | `imports/income.py` | `imports/income.py` |
| Isracard XLSX statement parsing | `imports/isracard.py` | `imports/isracard.py` |
| MAX XLSX statement parsing | `imports/max.py` | `imports/max.py` |
| Bank Leumi PDF text extraction and parsing | `imports/leumi.py` | `imports/leumi.py` |
| Statement format dispatch and XLSX provider detection | `imports/dispatch.py` | `imports/dispatch.py` |
| Import audit, deduplication and statement/income persistence | `imports/repository.py` | `imports/repository.py` |
| Staged category and display-identity reference data | `staging/references.py` | `staging/references.py` |
| Possible-duplicate candidate lookup | `staging/duplicates.py` | `staging/duplicates.py` |
| Statement coverage, prior-period warnings and coverage persistence | `staging/coverage.py` | `staging/coverage.py` |
| Staged transaction summaries and reconciliation totals | `staging/rules.py` | `staging/rules.py` |
| Staged merchant aggregation and database-first resolution suggestions | `staging/merchants.py` | `staging/merchants.py` |
| Per-file income and statement staging classification | `staging/file_analysis.py` | `staging/file_analysis.py` |
| Read-only staged-file analysis orchestration | `staging/analysis.py` | `staging/analysis.py` |
| Reviewed duplicate and merchant/transaction decision application | `staging/decisions.py` | `staging/decisions.py` |
| Staged-import backup and transactional commit orchestration | `staging/service.py` | `staging/service.py` |
| Multipart upload decoding and request-size validation | `http/multipart.py` | `http/multipart.py` |
| Bounded JSON-object request decoding | `http/json_body.py` | `http/json_body.py` |
| Standard JSON read and mutation route dispatch | `http/api.py` | `http/api.py` |
| Uploaded-file persistence and staged-session HTTP workflow | `http/imports.py` | `http/imports.py` |
| HTTP request/response mapping and static application serving | `http/handler.py` | `http/handler.py` |
| Billing/reporting month | Import engine and `reporting/sql.py` | Tested reporting domain |
| Period bounds and calendar-month arithmetic | `reporting/queries.py`, `reporting/periods.py` | Same |
| Income, net spending, amount left and monthly averages | `reporting/calculations.py` | `reporting/calculations.py` |
| Purchase-date activity and installment-plan collapsing | `reporting/purchase_activity.py` | `reporting/purchase_activity.py` |
| Category shares and previous-month comparisons | `reporting/categories.py` | `reporting/categories.py` |
| Category totals, card/routine scope and comparison assembly | `reporting/category_queries.py` | Same |
| Period/card and all-versus-routine transaction scope | `reporting/scope.py` | `reporting/scope.py` |
| Transaction browsing, filtering and complete-history search | `transactions/queries.py` | `transactions/queries.py` |
| Dashboard totals, cards, trend and response assembly | `reporting/dashboard.py` | `reporting/dashboard.py` |
| Reimbursement validation and personal-spending amount | `reporting/personal_spending.py` | `reporting/personal_spending.py` |
| Transaction category exceptions and reimbursement writes | `transactions/service.py` | `transactions/service.py` |
| Permanent merchant categories, display identities and per-alias category writes | `merchants/service.py` | `merchants/service.py` |
| Mapping review and grouped merchant-management reads | `merchants/queries.py` | `merchants/queries.py` |
| Category totals and routine scope | `server.py` | Reporting application/domain module |
| Recurring cadence, lifecycle, status, history and series amounts | `recurring/rules.py` | `recurring/rules.py` |
| Recurring database grouping and burden assembly | `recurring/queries.py` | `recurring/queries.py` |
| Recurring profile and alias-membership writes | `recurring/service.py` | `recurring/service.py` |
| Monthly and long-period observations | `dist/observations.js` | Backend observation domain; frontend presentation only |
| Reversible observation-review reads and writes | `observations/queries.py`, `observations/service.py` | Same |
| Event period visibility and query assembly | `events/queries.py` | `events/queries.py` |
| Event settings validation and selected/lifetime membership totals | `events/rules.py` | `events/rules.py` |
| Event creation, editing and transaction membership writes | `events/service.py` | `events/service.py` |
| Browser JSON and multipart API transport | `dist/api.js` | Typed frontend API client |
| Browser formatting, escaping, and calendar helpers | `dist/format.js` | Frontend shared utilities |
| Import display-identity normalization and matching | `dist/matching.js` | Frontend shared utilities |
| Transaction table columns and pure row sorting | `dist/transactions.js` | Frontend transaction feature |
| Event card grouping and client-side date/type validation | `dist/events.js` | Frontend events feature |
| Recurring table constants, status presentation and sorting | `dist/recurring.js` | Frontend recurring feature |
| Staged-import review decisions and preview assembly | `dist/import-review.js` | Frontend import feature |
| Category donut segments, hover lookup and comparison labels | `dist/categories.js` | Frontend dashboard feature |
| Modal state and dashboard interaction | `dist/app.js` | Vue components |

## Frontend shared-utility baseline

`dist/api.js` is now the single production transport boundary for JSON reads,
JSON mutations, multipart uploads and API-error propagation. `dist/app.js` and
`dist/observations.js` still own feature-specific URLs and payload assembly, but
do not call `fetch` directly.

`dist/format.js` is the shared, framework-independent boundary for currency and
date display, HTML escaping, month arithmetic and simple median/range helpers.
The dashboard and observation code no longer carry separate copies of these
helpers.

`dist/matching.js` owns the import review's framework-independent display-name
normalization, alias scoring, ranking and strong-unambiguous-match rule. Its
thresholds are unchanged and are now covered without requiring a browser DOM.

`dist/transactions.js` owns the transaction table's stable column definition,
composite sort values, numeric sorting and missing-value placement. Both the
complete transaction table and expanded category rows consume the same helper.

`dist/events.js` owns the pure event-card grouping used for repeated business
destinations, card ordering, business-trip type recognition and the existing
client-side date-order check. Rendering and modal state remain in `dist/app.js`.

`dist/recurring.js` owns recurring type/cadence choices, table definitions,
status labels/classes and pure series/commitment sorting. Rendering and all
persisted recurring-profile changes remain in `dist/app.js` and the backend.

`dist/import-review.js` owns the staged review's step definition, reconciliation
requirements, decision completeness checks, default merchant decision shape and
read-only transaction preview assembly. Upload, rendering and commit state remain
in `dist/app.js`; backend staging remains authoritative for import safety.

`dist/categories.js` owns the category panel's pure donut boundaries, gradient
model, pointer-angle lookup and month-over-month label selection. DOM updates,
tooltips and category navigation remain in `dist/app.js`.

The Vue migration should replace this compatibility client with a typed client
while preserving its tested request semantics. The old UI and Vue must not
control the same DOM subtree.

## Vue preview boundary

`frontend/` is the isolated Vue 3 + TypeScript + Vite source tree. Its build
writes to ignored `dist-next/`; it does not overwrite or modify production
`dist/`. The preview dev server is local-only on `127.0.0.1:5173` and proxies
`/api` to the existing local ClearSpend server on `127.0.0.1:8765`.

`frontend/src/api/client.ts` mirrors the production transport semantics with a
generic typed client. `frontend/src/api/contracts.ts` records backend-owned JSON
contracts, beginning with the categories read model, and `api/categories.ts`
owns its typed URL/query assembly.

The preview now owns its first complete read-only feature: the category panel.
`features/categories/CategoriesPanel.vue` loads the typed categories contract,
supports all-spending and routine-only scopes, and presents loading, failure,
empty, donut and previous-month-comparison states. Its pure donut/comparison
model intentionally mirrors the tested legacy helper until the production
category subtree is cut over and the duplicate legacy owner can be removed.

This ownership applies only inside the isolated preview application. No
production DOM subtree is Vue-owned yet, and `dist/` remains the authoritative
deployable UI.

The preview filter bar now provides the first shared read-only dashboard state:
period, reporting month and card. It obtains available months and card identities
from the existing typed dashboard response, preserves the current rule that
choosing a month returns to the monthly view, and passes the selected query to
the migrated category panel. This state is local to the preview and does not
persist or modify financial data.

The preview also renders the complete income-and-spending region from the
backend-owned `income_summary`: income, net spending, amount left, allocation
percentages and monthly averages. The browser only bounds the percentage bar
for display. Its eye control stores the same local privacy preference and does
not write financial state.

The four key-metric cards are also preview-owned. Their spent, refund,
transaction-count, daily-average and active-day values are displayed directly
from the backend `metrics` contract; the frontend only formats them and builds
the explanatory labels.

The preview Spending by card panel now renders the backend card summaries and
shares. Selecting a row changes only the shared preview card filter; it causes
the existing read-only queries to reload and does not persist any state.

The preview Spending trend is now migrated for both backend modes. Monthly
views render purchase-date category stacks, refunds and cumulative purchase
value; longer periods render backend monthly spending and optional household
income. The income privacy preference is shared preview state so hiding income
also removes it from this chart, matching the existing behavior.

The preview transaction browser now owns the read-only Recent transactions
panel and View all modal. It consumes the dashboard's six-row summary and the
typed `/api/transactions` contract, preserves the default transaction-date
descending sort, supports every displayed source column, and delegates
substring search to the backend. Browsing without a search remains capped at
1,000 rows; a non-empty query searches the complete history inside the selected
period and card. Category corrections, reimbursements and event assignment are
still production-owned write workflows and are deliberately absent here.

The preview Recurring & commitments region now consumes the typed
`/api/recurring` read model. It renders backend-owned recurring and installment
totals, spending composition, scrollable previews, sortable detail tables,
verdict summaries and actual billing history for monthly, latest-year and
all-time scopes. The preview deliberately excludes type, cadence, lifecycle and
merchant-membership mutations; those reviewed write workflows remain owned by
the production UI until they receive a separate migration checkpoint.

The preview Projects & events region now consumes the typed `/api/events`
contract. It renders period/card-filtered event cards, automatically groups
repeated business-trip destinations in longer periods, and presents lifetime
event totals, category breakdowns and exact transaction membership in a
read-only modal. Event creation, event settings and transaction assignment
remain production-owned write workflows and are not exposed by the preview.

The first observation-calculation slice now has a pure backend owner in
`observations/transaction_rules.py`: possible-duplicate grouping, reliable
six-month purchase baselines, large-purchase qualification, unusual-purchase
qualification, overlap merging and deterministic review keys. This module does
not query SQLite, format cards or serve an API response. The legacy browser
engine remains authoritative until the remaining observation families are
extracted and complete assembled-payload parity is proven.

The second observation-calculation slice is isolated in
`observations/monthly_rules.py`. It owns the amount-left decline rule and the
routine-category spending-increase rule, plus routine merchant-activity
changes. This includes their exact three-month coverage, active-month median
and combined threshold requirements. These pure calculations are also inactive
at the API boundary; production observation cards continue to use the unchanged
browser engine.

Reviewed recurring-payment amount qualification is isolated in
`observations/recurring_amount_rules.py`. It owns exact stream selection,
fixed-versus-variable comparisons, original-currency handling, fee wording and
the deliberately unconfirmed first-observed-fee result. It does not establish
statement coverage or activate API findings; the production browser remains
authoritative.

Monthly recurring occurrence qualification is isolated in
`observations/recurring_cycle_rules.py`. It learns an expected billing day from
the latest six prior charges, checks a seven-day window across calendar-month
boundaries, keeps exact alias/provider/card streams separate, suppresses
duplicate-only windows and produces deterministic review keys. It is not yet
wired into observation responses.

Fees outside reviewed recurring profiles are isolated in
`observations/standalone_fee_rules.py`. The rule uses canonical
merchant-and-category identity across the prior 12 months, excludes current
recurring charges to prevent duplicate cards, and preserves the distinction
between first observed and confirmed new. Coverage proof and response assembly
remain outside this pure rule.

The first long-period observation slice is isolated in
`observations/historical_rules.py`. It owns shared three-month change windows,
six-month baselines, lifecycle selection and the routine-spending shift rule,
including event and refund exclusions. It now also owns the three-tier
amount-left trend rule: repeated overspending, spending outgrowing income, and
consistent amount-left movement. It also owns lasting category-routine shifts,
including asymmetric increase/decrease eligibility, covered zero-spend months,
event exclusions and transaction-specific merchant drivers. Backend results
now also qualify recurring-burden shifts by normalized monthly cost and active
service count, with combined findings and started, ended and amount-changed
service evidence. Persistent installment burden now has a pure owner too,
including six-month qualification, plan-identity replacement evidence and the
separate persistent-without-replacement result. These rules remain inactive
until all historical families and assembled-payload parity are complete.

Long-period merchant habits are being isolated separately in
`observations/historical_merchant_rules.py`. The first slice detects merchants
that became regular through either sustained monthly spending or repeated
purchase frequency, using purchase dates and excluding reviewed recurring
aliases, events, installments, transfers and refunds. Later frequency and
typical-purchase shifts now share that eligibility boundary and preserve four
separate outcomes: buying more, buying less, typical amount increased and
typical amount decreased. Newly regular merchants are excluded from this
second pass so one behavior is not reported twice. Grouping and payload
assembly remain in the legacy engine.

Framework-independent observation-card grouping is now isolated in
`observations/grouping.py`. It owns score ordering, card priority, repeated
entity summaries, compact category groups and the all-regular versus mixed
merchant-habit presentation model. It returns typed values without HTML; the
legacy browser still performs active production grouping until backend finding
assembly is complete and parity-tested.

Reversible observation-review policy is centralized in
`observations/policy.py`. It defines the only three reviewable observation
types, their persisted resolutions, labels, activity targets and transaction
cardinality. The existing persistence workflow consumes the same resolution
map; factual observations remain deliberately non-reviewable.

Persisted review state can now be applied by the pure grouping boundary before
cards are assembled. A reviewed keyed finding is suppressed, remaining grouped
findings are regrouped, and a fully reviewed group disappears. Unkeyed factual
findings always remain visible. The browser still performs this step in
production until the backend observation response is introduced.

Observation period orchestration is isolated in `observations/scope.py`. It
separates target months from earlier transaction history and recurring-snapshot
coverage for Month, Latest year and All time views, while preserving the
selected-month fallback and empty-month behavior. No database reads or HTTP
responses depend on it yet.

The read-only observation input snapshot is assembled in
`observations/inputs.py` from existing reporting, transaction, recurring and
review read models. It reproduces the source payload set currently fetched by
the browser: month-indexed transaction history, recurring snapshots, all-card
household history, partial-month state, income visibility and active review
keys. It is not exposed through HTTP and deliberately introduces no new SQL.

## Known compatibility and audit targets

- Preserve `127.0.0.1` as the default bind address.
- Validate the full application on Python 3.13 before documenting it as supported;
  multipart uploads no longer depend on the removed `cgi` module.
- Preserve the staged analyze/commit workflow and pre-import backup.
- Review the legacy direct-import route separately.
- Standardize error mapping after use cases are extracted.
- Audit dynamic `innerHTML` paths without claiming an unverified vulnerability.
- Keep current SQL parameterized; no confirmed SQL-injection defect was found in
  this architectural inventory.
- Treat `dist/` as production source until the Vue build has passed an explicit
  cutover.

## Baseline test status

- Tracked synthetic suite: `tests/synthetic/`
- Tracked dependency-free frontend shared-utility suite: `tests/frontend/`
- Private statement-derived regression tests: ignored local files under `tests/`
- Baseline at introduction: 7 synthetic tests and 39 total local tests passing
- Current refactoring checkpoint: 280 synthetic tests and 312 total Python tests passing, plus 40 frontend tests
- Current frontend shared-utility checkpoint: 40 tests passing
- Current Vue preview checkpoint: 31 typed category/filter/income/metric/card/trend/transaction/recurring/event tests passing

This inventory should be updated only when an intentional contract or ownership
change is reviewed and accepted.
