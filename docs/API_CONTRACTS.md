# Local API contracts

This document describes the maintained browser/server boundary. The Python
server owns runtime validation and financial behavior; TypeScript interfaces in
`frontend/src/api/contracts/` describe expected responses but are not runtime
validators.

## Transport and compatibility

- The application serves JSON below `/api` from the same local process that
  serves `dist/`.
- Successful JSON responses use `Cache-Control: no-store`.
- Reviewed validation failures normally return `400`. Unexpected failures
  return a stable generic `500` response, while a busy or unavailable database
  returns a safe `503` response. Detailed exceptions are logged by the local
  server and are never returned to the browser.
- `GET /api/health` returns the API compatibility identifier required by the
  frontend. An incompatible or stale server causes the UI to withhold its data
  panels and request a restart.
- Standard JSON operations use `frontend/src/api/client.ts`. Import uploads use
  the same error semantics with multipart request bodies.

## Read endpoints

| Method and path | Inputs | Response responsibility |
| --- | --- | --- |
| `GET /api/health` | None | Runtime status, database availability, compatibility ID |
| `GET /api/dashboard` | `period`, `card`, `month` | Metrics, income summary, cards, categories, recent rows, trend and coverage context |
| `GET /api/transactions` | `period`, `card`, `month`, `q`, `category`, `event_scope` | Sortable transaction detail rows and complete-history scoped search |
| `GET /api/categories` | `period`, `card`, `month`, `event_scope` | Category totals, shares and previous-month comparisons |
| `GET /api/mapping` | None | Mapping review data |
| `GET /api/merchants` | None | Display identities, aliases, categories and recurring context |
| `GET /api/recurring` | `view`, `period`, `card`, `month` | Reviewed recurring overview or three-month Upcoming forecast |
| `GET /api/events` | `period`, `card`, `month` | Visible events, groups, exact membership and assignment choices |
| `GET /api/observations` | `period`, `card`, `month`, `income_hidden` | Backend-qualified monthly findings or long-period patterns |
| `GET /api/observation-reviews` | None | Active reversible review decisions |

`period` accepts `month`, `year`, or `all`. `event_scope` accepts `all` or
`routine`. Backend query and calculation modules remain authoritative for
scope, totals, qualification, and exclusions.

For `/api/recurring`, `view` accepts `overview` or `upcoming` and defaults to
`overview`. Overview uses `period`, `card`, and `month` as before. Upcoming uses
only `card`; its horizon is the current application month plus the next two
months. Each month returns expected, confirmed, and forecast totals, unknown
amount counts, and payment rows. Payment rows expose an opaque
`occurrence_id`, never a source transaction key. Evidence fields distinguish
confirmed values, estimates, and unknown values. Projected payments also expose
nullable `amount_confidence`: `provisional` for one payment, `developing` for
two similar payments, or `established` for a supported stable component.
Unresolved schedules are returned separately and do not contribute to totals.
`generated_as_of` and `selected_card` remain response metadata so the
time-sensitive result is auditable and its scope is self-describing. Upcoming
does not expose transaction category or internal recurring/installment source
identifiers; `occurrence_id` and `source_kind + source_id` provide the public
row and unresolved-source identities.

## Mutation endpoints

| Method and path | Purpose and persistent effect |
| --- | --- |
| `POST /api/mapping` | Save an exact normalized merchant category rule |
| `POST /api/merchants` | Save a display identity and reviewed per-alias categories |
| `POST /api/transaction-category` | Save a category exception for one transaction |
| `POST /api/transaction-adjustment` | Add, update, or remove one reimbursement adjustment |
| `POST /api/transaction-event` | Assign or unassign one exact transaction from an event |
| `POST /api/events` | Create an event without automatically assigning transactions |
| `POST /api/event-settings` | Edit event identity and period-visibility settings |
| `POST /api/recurring-profile` | Edit recurring type, cadence, and lifecycle |
| `POST /api/recurring-profile/manage` | Save reviewed recurring membership and alias inclusion |
| `POST /api/observation-review` | Save or undo an allowed finding resolution |

These writes preserve the separations documented in `ARCHITECTURE.md`:
merchant category, display identity, transaction category exception,
reimbursement, event membership, recurring membership, and observation review
are independent persisted concepts.

## Staged import endpoints

- `POST /api/import/analyze` accepts exactly one XLSX or PDF statement per
  staged session. It parses and previews without changing live financial data.
- `POST /api/import/commit` revalidates the staged statement and reviewed
  decisions, creates a verified encrypted PostgreSQL backup, and atomically
  commits the approved mappings, transactions, duplicate links, coverage and
  audit rows.
- `POST /api/import/cancel` removes the temporary staged session without live
  database writes.

One workbook may contain several provider tabs or cards. A second statement
requires a new staged session. The retired direct-import route is not a
production API.

## Contract ownership

- Route decoding and HTTP status mapping: `src/clearspend/http/`.
- Read models and financial results: feature query/reporting packages under
  `src/clearspend/`.
- Writes: feature service modules; staged imports additionally use
  `src/clearspend/staging/service.py` for their transaction boundary.
- Browser transport: `frontend/src/api/`.
- Browser compile-time contracts: `frontend/src/api/contracts/` with
  `frontend/src/api/contracts.ts` as a compatibility export barrel.

When an endpoint changes, update its Python contract tests, TypeScript contract,
consumer tests, and this document. Do not duplicate authoritative financial
rules here; link to the applicable domain document.
