# Refactoring baseline

This document began as the pre-refactor runtime inventory and now records the
contracts preserved by the completed backend extraction and Vue production
cutover. Historical sections are labelled where they describe the retired
vanilla client. All examples and tests associated with this baseline must use
synthetic data.

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
| `GET /api/observations` | `period`, `card`, `month`, `income_hidden` | `observations_payload` | Backend-qualified findings and grouped cards |
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
| Monthly and long-period observations | `observations/` backend package | Backend observation domain; frontend presentation only |
| Reversible observation-review reads and writes | `observations/queries.py`, `observations/service.py` | Same |
| Event period visibility and query assembly | `events/queries.py` | `events/queries.py` |
| Event settings validation and selected/lifetime membership totals | `events/rules.py` | `events/rules.py` |
| Event creation, editing and transaction membership writes | `events/service.py` | `events/service.py` |
| Browser JSON and multipart API transport | Typed client in `frontend/src/api/` | Same |
| Browser formatting and calendar helpers | `frontend/src/shared/` | Same |
| Import display-identity normalization and matching | `frontend/src/features/imports/` | Same |
| Transaction table columns and sorting | `frontend/src/features/transactions/` | Same |
| Event card grouping and date/type validation | `frontend/src/features/events/` | Same |
| Recurring table constants, status presentation and sorting | `frontend/src/features/recurring/` | Same |
| Staged-import review decisions and preview assembly | `frontend/src/features/imports/` | Same |
| Category donut segments, hover lookup and comparison labels | `frontend/src/features/categories/` | Same |
| Modal state and dashboard interaction | Vue components | Same |

## Retired vanilla-client baseline

The following files describe the former production client. They are retained
only as test fixtures under `tests/frontend/legacy/` so the Vue implementation
can continue proving compatibility with the established pure rules. They are
not served by the application and must not be treated as production source.

`dist/api.js` was the vanilla transport boundary for JSON reads, JSON
mutations, multipart uploads and API-error propagation. `dist/app.js` and the
observation client owned feature-specific URLs, and
`dist/observation-client.js` owned the consolidated observation URL.

`dist/format.js` was the shared, framework-independent boundary for currency and
date display, HTML escaping, month arithmetic and simple median/range helpers.
The dashboard and observation code no longer carry separate copies of these
helpers.

`dist/matching.js` owned the import review's framework-independent display-name
normalization, alias scoring, ranking and strong-unambiguous-match rule. Its
thresholds are unchanged and are now covered without requiring a browser DOM.

`dist/transactions.js` owned the transaction table's stable column definition,
composite sort values, numeric sorting and missing-value placement. Both the
complete transaction table and expanded category rows consume the same helper.

`dist/events.js` owned the pure event-card grouping used for repeated business
destinations, card ordering, business-trip type recognition and the existing
client-side date-order check.

`dist/recurring.js` owned recurring type/cadence choices, table definitions,
status labels/classes and pure series/commitment sorting.

`dist/import-review.js` owned the staged review's step definition, reconciliation
requirements, decision completeness checks, default merchant decision shape and
read-only transaction preview assembly.

`dist/categories.js` owned the category panel's pure donut boundaries, gradient
model, pointer-angle lookup and month-over-month label selection.

The Vue application has replaced this compatibility client. Its typed API and
feature models preserve the tested request and calculation semantics; there is
only one production UI owner.

## Vue production boundary

`frontend/` is the Vue 3 + TypeScript + Vite source tree. Its production build
writes generated assets to `dist/`, which is served by the local application.
The optional development server is local-only on `127.0.0.1:5173` and proxies
`/api` to the existing local ClearSpend server on `127.0.0.1:8765`.

`frontend/src/api/client.ts` mirrors the production transport semantics with a
generic typed client. `frontend/src/api/contracts.ts` records backend-owned JSON
contracts, beginning with the categories read model, and `api/categories.ts`
owns its typed URL/query assembly.

The Vue application owns the category panel.
`features/categories/CategoriesPanel.vue` loads the typed categories contract,
supports all-spending and routine-only scopes, and presents loading, failure,
empty, donut and previous-month-comparison states. Its pure donut/comparison
model preserves the previously tested category behavior.

The Vue filter bar provides shared dashboard state:
period, reporting month and card. It obtains available months and card identities
from the existing typed dashboard response, preserves the current rule that
choosing a month returns to the monthly view, and passes the selected query to
the migrated category panel. This state is local to the browser and does not
persist or modify financial data.

The Vue application also renders the complete income-and-spending region from the
backend-owned `income_summary`: income, net spending, amount left, allocation
percentages and monthly averages. The browser only bounds the percentage bar
for display. Its eye control stores the same local privacy preference and does
not write financial state.

The four key-metric cards are also Vue-owned. Their spent, refund,
transaction-count, daily-average and active-day values are displayed directly
from the backend `metrics` contract; the frontend only formats them and builds
the explanatory labels.

The Spending by card panel renders the backend card summaries and
shares. Selecting a row changes only the shared card filter; it causes
the existing read-only queries to reload and does not persist any state.

The Spending trend is migrated for both backend modes. Monthly
views render purchase-date category stacks, refunds and cumulative purchase
value; longer periods render backend monthly spending and optional household
income. The income privacy preference is shared browser state so hiding income
also removes it from this chart, matching the existing behavior.

The transaction browser owns the read-only Recent transactions
panel and View all modal. It consumes the dashboard's six-row summary and the
typed `/api/transactions` contract, preserves the default transaction-date
descending sort, supports every displayed source column, and delegates
substring search to the backend. Browsing without a search remains capped at
1,000 rows; a non-empty query searches the complete history inside the selected
period and card. Event assignment and transaction-specific category correction
are migrated as typed mutations. A category correction uses the permanent
merchant vocabulary but writes only a transaction override, leaving the
merchant rule and future imports unchanged. Reviewed full and partial
reimbursements are also migrated: the original charge stays intact, only the
personal-spending adjustment is written, and an existing adjustment can be
removed independently.

The Recurring & commitments region consumes the typed
`/api/recurring` read model. It renders backend-owned recurring and installment
totals, spending composition, scrollable previews, sortable detail tables,
verdict summaries and actual billing history for monthly, latest-year and
all-time scopes. Type and cadence edits are migrated as typed writes from the
recurring-series table and refresh all affected read models after saving.
Lifecycle editing is also migrated in the selected-series inspector: selection
is staged until an explicit save, and ended profiles require an end month. The
dedicated recurring-rules manager now owns reviewed alias membership, adding a
merchant to recurring tracking, and the confirmed not-recurring decision. These
changes affect recurring analysis only; transactions and merchant identities
remain intact.

The Projects & events region consumes the typed `/api/events`
contract. It renders period/card-filtered event cards, automatically groups
repeated business-trip destinations in longer periods, and presents lifetime
event totals, category breakdowns and exact transaction membership in a
read-only modal. Event creation is migrated with typed validation for dates,
budget and business-trip destinations; it creates the event without assigning
transactions automatically. Transaction assignment is owned by the transaction
browser and refreshes this read model after a save. Editing existing event
settings is also migrated: name, type, business destination, dates, budget and
status update presentation and period visibility without changing exact
transaction membership.

The Financial observations region consumes the typed consolidated
`/api/observations` contract. It renders backend-qualified monthly findings and
long-period patterns, established card identities, grouped-card summaries and
source evidence in a details modal. It never recalculates eligibility or
thresholds. The three deliberately reviewable types can save or undo the same
local reversible decisions as production; factual cards remain read-only.
Activity-navigation delegates to the existing Vue feature owners: exact or
merchant-matched transactions open in the transaction modal, category shifts
open routine-spending transactions, recurring findings open the applicable
series or commitments view, and income findings focus the income panel.

The first observation-calculation slice has a pure backend owner in
`observations/transaction_rules.py`: possible-duplicate grouping, reliable
six-month purchase baselines, large-purchase qualification, unusual-purchase
qualification, overlap merging and deterministic review keys. This module does
not query SQLite, format cards or serve an API response. It participates in the
assembled backend workflow after complete cross-engine parity was proven.

The second observation-calculation slice is isolated in
`observations/monthly_rules.py`. It owns the amount-left decline rule and the
routine-category spending-increase rule, plus routine merchant-activity
changes. This includes their exact three-month coverage, active-month median
and combined threshold requirements. These pure calculations feed the active
read-only observation API.

Reviewed recurring-payment amount qualification is isolated in
`observations/recurring_amount_rules.py`. It owns exact stream selection,
fixed-versus-variable comparisons, original-currency handling, fee wording and
the deliberately unconfirmed first-observed-fee result. It does not establish
statement coverage; the assembled workflow supplies that context.

Monthly recurring occurrence qualification is isolated in
`observations/recurring_cycle_rules.py`. It learns an expected billing day from
the latest six prior charges, checks a seven-day window across calendar-month
boundaries, keeps exact alias/provider/card streams separate, suppresses
duplicate-only windows and produces deterministic review keys. It feeds the
assembled monthly observation response.

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
service evidence. Persistent installment burden has a pure owner too,
including six-month qualification, plan-identity replacement evidence and the
separate persistent-without-replacement result. These rules now feed the
assembled historical response.

Long-period merchant habits are isolated separately in
`observations/historical_merchant_rules.py`. The first slice detects merchants
that became regular through either sustained monthly spending or repeated
purchase frequency, using purchase dates and excluding reviewed recurring
aliases, events, installments, transfers and refunds. Later frequency and
typical-purchase shifts now share that eligibility boundary and preserve four
separate outcomes: buying more, buying less, typical amount increased and
typical amount decreased. Newly regular merchants are excluded from this
second pass so one behavior is not reported twice. Backend presentation and
grouping assemble these findings for the consolidated response.

Framework-independent observation-card grouping is now isolated in
`observations/grouping.py`. It owns score ordering, card priority, repeated
entity summaries, compact category groups and the all-regular versus mixed
merchant-habit presentation model. It returns typed values without HTML and is
used by the active backend workflow as well as the browser fallback.

Reversible observation-review policy is centralized in
`observations/policy.py`. It defines the only three reviewable observation
types, their persisted resolutions, labels, activity targets and transaction
cardinality. The existing persistence workflow consumes the same resolution
map; factual observations remain deliberately non-reviewable.

Persisted review state can now be applied by the pure grouping boundary before
cards are assembled. A reviewed keyed finding is suppressed, remaining grouped
findings are regrouped, and a fully reviewed group disappears. Unkeyed factual
findings always remain visible. The backend applies this step before returning
the active observation response; the browser fallback preserves the same rule.

Observation period orchestration is isolated in `observations/scope.py`. It
separates target months from earlier transaction history and recurring-snapshot
coverage for Month, Latest year and All time views, while preserving the
selected-month fallback and empty-month behavior. The read service uses this
scope for the production response.

The read-only observation input snapshot is assembled in
`observations/inputs.py` from existing reporting, transaction, recurring and
review read models. It reproduces the source payload set currently fetched by
the browser: month-indexed transaction history, recurring snapshots, all-card
household history, partial-month state, income visibility and active review
keys. It remains an internal application input and deliberately introduces no
new SQL.

Long-period rule invocation is now coordinated by the pure typed boundary in
`observations/historical_analysis.py`. It preserves reporting-month activity
for household, category and commitment analysis while keeping purchase-date
activity separate for merchant habits. The coordinator returns qualified raw
signals in established card-priority order; it does not create presentation
text, query the database or expose an endpoint directly.

`observations/historical_inputs.py` adapts the existing read-only snapshot to
that coordinator without another database query. Reporting months remain the
source for spending, category and commitment trends, while transaction dates
remain the source for merchant-habit months. Recurring aliases and lifecycle
state are normalized once at this boundary. The read service invokes this
internal adapter/analyzer for historical requests.

Historical installment analysis now receives a dedicated internal read model
from `observations/historical_queries.py`. Its stable plan identity includes
card, canonical merchant, original purchase date, original amount, currency and
installment count, so two plans at one merchant are not merged accidentally.
This query is not exposed in the public recurring response and performs no
writes.

Qualified long-period signals are mapped to the shared observation-finding and
group models by `observations/historical_presentation.py`. This boundary owns
labels, explanatory comparisons, evidence rows and the established top-twelve
merchant surface limit, but never recalculates eligibility. Grouping and active
review suppression reuse the framework-independent grouping module. It now
provides the historical presentation layer behind the production route.

Single-month rule invocation is now coordinated by the pure typed boundary in
`observations/monthly_analysis.py`. It preserves the production precedence for
possible duplicates, reviewed recurring charges, additional billing-cycle
charges, routine merchant activity, large and unusual purchases, and standalone
fees. Exact recurring alias-plus-category membership, event exclusions,
partial-month suppression and the distinction between routine spending and all
positive personal spending are explicit inputs. The coordinator returns raw
signals only; it does not query SQLite, format cards, expose an endpoint or
own transport concerns.

`observations/monthly_inputs.py` adapts the existing read-only monthly snapshot
to that coordinator without another database query. It preserves reporting
month separately from purchase date, normalizes charged and personal amounts,
retains original-currency evidence, and uses the target month's reviewed
recurring profiles. Purchase-date fallback follows the browser's established
transaction-date, billing-date, reporting-month order. The combined adapter
and analyzer remain internal application boundaries used by the read service.

Qualified single-month signals are mapped to the shared finding and card-group
models by `observations/monthly_presentation.py`. It preserves actionable
metadata for the three reviewable finding types, including transaction IDs,
recurring-series identity, occurrence dates and event labels. Explanatory text,
comparison values and evidence are derived from already-qualified signals and
their read-only source rows; eligibility is not recalculated. Active review
suppression and grouping reuse the framework-independent grouping boundary.

Monthly and historical paths now meet in the read-only application workflow in
`observations/read_service.py`. It chooses the typed analysis boundary from the
snapshot period, applies review suppression consistently, and returns one view
model with active findings and grouped cards. `observations/payloads.py`
serializes that view using the established browser finding and group field
names, while leaving visual color and icon ownership in the frontend. The
read-only `/api/observations` route exposes this contract after exact
cross-engine parity was established. The Vue production frontend consumes it
as its authoritative source.

Cross-engine comparison has a durable synthetic harness. The tracked Node
reference runner uses the retired rule fixture in `tests/frontend/legacy/` and
receives only synthetic or locally assembled ignored inputs.
`observations/parity.py` reports three
tiers independently: qualified finding identity, grouped card types and full
presentation/evidence. This prevents wording differences from hiding a rule
disagreement and prevents matching counts from hiding different findings.

The local all-card and per-card parity audit now matches qualified findings,
grouped card types and complete finding payloads in all 21 tested month,
latest-year and all-time scopes. Complete payload parity includes presentation,
evidence, scores, review metadata and event context. That audit is the basis for
the production frontend cutover to the read-only route. The audit also
established that event membership is
exposed as a stable text slug, not only a numeric ID; adapters must preserve
either representation so event spending is never folded back into routine
observations.

## Known compatibility and audit targets

- Preserve `127.0.0.1` as the default bind address.
- Python 3.13 runs all 337 tracked synthetic tests successfully; a complete
  private-fixture run additionally requires installing the pinned `pypdf`
  dependency into that interpreter's environment.
- Preserve the staged analyze/commit workflow and pre-import backup.
- Review the legacy direct-import route separately.
- Continue standardizing error mapping when new use cases are extracted.
- Keep current SQL parameterized; no confirmed SQL-injection defect was found in
  this architectural inventory.
- Treat `frontend/` as production source and `dist/` as generated output.

## Baseline test status

- Tracked synthetic suite: `tests/synthetic/`
- Tracked dependency-free frontend shared-utility suite: `tests/frontend/`
- Private statement-derived regression tests: ignored local files under `tests/`
- Baseline at introduction: 7 synthetic tests and 39 total local tests passing
- Current refactoring checkpoint: 337 synthetic tests and 369 total Python tests passing, plus 43 legacy-compatibility frontend tests
- Current legacy shared-utility compatibility checkpoint: 43 tests passing
- Current Vue production checkpoint: 62 typed category/filter/income/metric/card/trend/transaction/import/merchant/recurring/event/observation tests passing

This inventory should be updated only when an intentional contract or ownership
change is reviewed and accepted.
