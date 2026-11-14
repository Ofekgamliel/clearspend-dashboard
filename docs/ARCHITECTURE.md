# ClearSpend architecture

This document is the living contract for ClearSpend's runtime, module ownership,
dependency boundaries, state ownership, and development workflow. Detailed
financial behavior belongs in the domain documents linked from
[`README.md`](README.md).

## System overview

ClearSpend is a local-first modular monolith for importing and understanding
personal financial records. A Vue browser application, Python HTTP server, and
one SQLite database run on the same computer. GitHub stores application code,
never the user's financial state.

The system is intentionally not a cloud service or collection of microservices.
No production frontend asset may contain real transactions, merchants, amounts,
income, dates, card suffixes, or statement-derived fixtures.

## Technology decisions

| Area | Current decision |
| --- | --- |
| Frontend | Vue 3, TypeScript and Vite under `frontend/` |
| Backend | Python standard-library `ThreadingHTTPServer` with modular application packages under `src/clearspend/` |
| Storage | One local SQLite database with explicit versioned migrations |
| Production assets | Generated Vite output under tracked `dist/` |
| Backend tests | `unittest` with synthetic temporary databases |
| Frontend tests | Node tests, Vue type/unit tests, Playwright E2E and reviewed visual snapshots |

Pinia, FastAPI, cloud storage, and separate services are not adopted. Add a new
dependency only for a demonstrated requirement, not architectural symmetry.

## Runtime and data flow

```text
Vue feature component
  -> frontend/src/api client and typed contract
  -> src/clearspend/http request decoding and response mapping
  -> feature query or application service
  -> pure financial rules and/or scoped SQLite access
  -> data/clearspend.db
```

Statement imports have a deliberately stronger boundary:

```text
one upload
  -> provider recognition and canonical parsing
  -> staged duplicate/coverage/merchant/reconciliation analysis
  -> explicit user decisions and complete insertion preview
  -> revalidation + verified SQLite backup
  -> one approved database transaction
  -> commit everything or roll everything back
```

The real application starts with:

```bash
PYTHONPATH=src:. .venv/bin/python -m clearspend.server --port 8765
```

`python3 -m http.server` serves static files only and cannot provide database or
API behavior.

## Repository structure

| Path | Responsibility |
| --- | --- |
| `frontend/src/` | Editable Vue production source |
| `frontend/src/features/` | Feature rendering, interaction and transient UI state |
| `frontend/src/api/` | Central browser transport and compile-time response contracts |
| `frontend/src/shared/` | Genuinely reused presentation utilities |
| `frontend/e2e/` | Synthetic browser workflows and visual baselines |
| `dist/` | Generated production assets; never hand-authored UI source |
| `src/clearspend/http/` | HTTP decoding, dispatch, compatibility and static serving |
| `src/clearspend/imports/` | Canonical import domain, provider parsers and persistence primitives |
| `src/clearspend/staging/` | Read-only review analysis and approved import orchestration |
| `src/clearspend/database/` | Connections, backups, schema and migrations |
| `src/clearspend/<feature>/` | Feature queries, pure rules and write services |
| `tests/synthetic/` | Tracked backend tests using synthetic temporary data |
| `tests/frontend/` | Tracked framework-independent compatibility tests |
| `docs/` | Current documentation and archived project history |
| `data/`, `samples/`, `analysis/` | Private ignored local state and research |

## Backend module boundaries

| Capability | Owner | Responsibility and boundary |
| --- | --- | --- |
| HTTP | `http/` | Decode and validate transport input, dispatch operations, map statuses/errors; no SQL or financial thresholds |
| Provider parsing | `imports/isracard.py`, `max.py`, `leumi.py`, `income.py` | Translate external formats into canonical candidates; never write SQLite directly |
| Import persistence | `imports/repository.py` | Import audit, transaction identity and persistence primitives |
| Staged review | `staging/` | Preview, duplicates, coverage, merchant suggestions, reviewed decisions and atomic commit orchestration |
| Reporting | `reporting/` | Period/card/event scope, categories, totals, income, trends and dashboard assembly |
| Transactions | `transactions/` | Complete browsing/search reads and transaction-specific category/reimbursement writes |
| Merchants | `merchants/` | Permanent category and display-identity reads/writes |
| Recurring | `recurring/` | Reviewed recurring membership, cadence, lifecycle, history and burden |
| Events | `events/` | Event visibility, exact membership, creation and settings |
| Observations | `observations/` | Pure qualification rules, input adapters, presentation, review policy and consolidated reads |
| Database | `database/` | Connections, verified backups, current schema and explicit migration runner |

The current code uses feature query modules for SQLite reads and feature service
modules for writes. Do not introduce repository interfaces for every table
merely for naming consistency. A service coordinates the transaction boundary
when several writes form one business operation; staged import is the clearest
example.

Pure financial-rule modules accept values and must be testable without an HTTP
server or database connection. Query and presentation modules may adapt stored
data to those rules but must not silently create a second eligibility policy.

## Frontend module boundaries

- `App.vue` owns composition and explicit cross-feature navigation only.
- `features/dashboard/useDashboardData.ts` owns shared filter loading,
  compatibility health, refresh revision and dashboard response state.
- `features/management/ManageDataMenu.vue` owns its menu and focus lifecycle.
- Each directory under `features/` owns its rendering, user interaction and
  feature-local presentation model.
- The transaction feature separates recent summary, complete browser, category
  correction, reimbursement editing, detail tables and feature CSS.
- `api/client.ts` is the common transport. Contracts are split by domain under
  `api/contracts/`; `api/contracts.ts` is only a compatibility export barrel.
- `shared/` is for code already reused across features, not a destination for
  helpers that might someday be shared.

Use component-local state by default and a feature composable when several
components share one feature workflow. Introduce global state management only
after multiple independent feature roots require coordinated state. Do not move
the old monolith into `App.vue`, one giant component, or one giant composable.

Feature components may format and arrange backend results, calculate bounded
display geometry, and manage draft form values. They must not independently
reimplement authoritative totals, observation thresholds, import identity, or
other financial policy.

## Dependency rules

### Enforced by structure and tests

- Provider parsers return canonical candidates and do not persist them.
- Production UI is authored in `frontend/src/`; `dist/` is generated.
- Browser API calls use the centralized transport and typed contracts.
- Staged analysis is separate from the approved atomic import commit.
- Schema changes use the migration mechanism and verified backups.

### Required design rules

- HTTP modules must not execute direct SQL or own financial thresholds.
- Pure financial rules must not import HTTP or open SQLite connections.
- Feature query/service modules must not depend on frontend code.
- Vue features must not create competing financial calculations or hidden API
  pathways.
- Avoid circular feature imports; coordinate cross-feature navigation at the
  application composition boundary.
- Put feature-specific CSS beside the feature when practical. Keep global CSS
  for application layout, shared tokens and older rules awaiting incremental
  extraction.

Some dependency rules are reviewed conventions rather than lint-enforced
constraints. Do not claim automated enforcement unless the check runs in CI.

## State and financial ownership

SQLite is authoritative for imported transactions, mappings, display
identities, transaction overrides, reimbursements, event membership, recurring
profiles, import coverage and observation reviews. Python owns reporting totals,
financial qualification, duplicate identity and approved write behavior.

Vue owns transient selections, open/closed UI, form drafts, sorting, focus,
privacy preference presentation and display transforms. A browser refresh key
invalidates affected feature reads after a successful mutation; it is not a
second financial database.

Merchant category, display identity, transaction category exception,
reimbursement, event membership, recurring membership and observation review
are independent concepts. Do not merge them for implementation convenience.

## Database and write rules

The default private database is `data/clearspend.db`. Its main persisted concepts
are defined by the current schema, including `schema_migrations`, imports,
transactions, mappings, overrides, adjustments, income, recurring profiles,
events, import coverage and observation reviews.

Before a migration, bulk category/mapping rewrite, duplicate repair or other
material mutation:

1. Create and verify an SQLite-consistent backup.
2. Record relevant before-counts and totals.
3. Use one transaction when the operation must succeed as a unit.
4. Preserve original provider evidence and reviewed decisions.
5. Verify integrity, counts, totals and representative records afterward.

See [`DATABASE_MIGRATIONS.md`](DATABASE_MIGRATIONS.md) and
[`OPERATIONS_AND_RECOVERY.md`](OPERATIONS_AND_RECOVERY.md). Never silently
rebuild or replace the live database.

## Feature ownership matrix

| Change | Frontend owner | Backend owner | Primary tests/docs |
| --- | --- | --- | --- |
| Read-only dashboard panel | `features/<feature>/` | relevant `reporting/` or feature query | Vue model/component, HTTP/reporting tests, UI guide |
| Transaction editor | `features/transactions/` | `transactions/service.py` | transaction service + Playwright workflow |
| Merchant mapping | `features/merchants/` | `merchants/` | merchant query/service + import rules |
| Recurring behavior | `features/recurring/` | `recurring/` | recurring rule/query/service + reporting rules |
| Observation | `features/observations/` | `observations/` | pure rule, presentation, read-service and E2E tests |
| Statement provider | import review consumer if needed | `imports/<provider>.py`, `dispatch.py` | parser/import fixtures + import rules |
| Staged review | `features/imports/` | `staging/`, `http/imports.py` | failure/rollback and complete E2E import workflow |
| Event | `features/events/` and transaction assignment | `events/` | event rules/query/service + E2E writes |
| Schema change | contract/UI only if exposed | `database/migrations/` | migration tests + migration guide |

## Adding or changing a feature

1. Identify the existing owner and read this document plus the applicable
   domain specification.
2. Confirm whether the change belongs in a component, composable, query,
   service, pure rule, parser, migration, or typed API contract.
3. Preserve one authoritative financial rule and one supported API path.
4. Add the smallest relevant pure, query/service, HTTP, Vue or browser tests.
5. Run the checks in [`TESTING.md`](TESTING.md).
6. Update `API_CONTRACTS.md` for exchanged semantics, the owning domain document
   for behavioral changes, and this file only for responsibility or dependency
   changes.
7. Record a current exception explicitly rather than describing a desired rule
   as already enforced.

Examples:

- A new dashboard panel gets a feature component and backend-owned read model;
  it does not calculate new financial totals in Vue.
- A new statement provider adds a canonical parser and dispatch recognition,
  then participates in the existing staged workflow rather than adding another
  import route.
- A new observation starts with a pure backend qualification rule, then input,
  presentation and API tests; Vue renders the returned finding.
- A new database field uses an ordered migration and verified backup path, not
  opportunistic `ALTER TABLE` code during ordinary startup.

## Documentation ownership

`ARCHITECTURE.md` owns module structure and allowed dependencies. Domain
documents own financial behavior. `API_CONTRACTS.md` owns exchanged HTTP
semantics. `OPERATIONS_AND_RECOVERY.md` owns runtime recovery. `AGENTS.md` is a
concise work policy and navigation layer.

Architectural boundary changes require an update here in the same pull request.
Behavioral changes update only their authoritative domain document. Historical
records under `archive/` provide context and never override maintained
documentation. Verify local Markdown links before merging documentation
changes.
