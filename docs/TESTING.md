# Testing and change acceptance

ClearSpend tests must use synthetic or temporary data unless a local ignored
regression test explicitly uses private fixtures. Never commit statement-derived
fixtures, database copies, screenshots, merchants, amounts, or card details.

## Tracked backend tests

Run the synthetic suite for applicable backend, API, reporting, import, or
database changes:

```bash
PYTHONPATH=src:. .venv/bin/python -m unittest discover -s tests/synthetic -v
```

The suite covers pure financial rules, query/service behavior, HTTP contracts,
staged-import failure and rollback paths, migrations, duplicate handling, and
synthetic reporting behavior.

When ignored private regression fixtures are available, the broader local suite
may also be run:

```bash
PYTHONPATH=src:. .venv/bin/python -m unittest discover -s tests -v
```

Private local tests can age independently of tracked CI. A failure caused by a
stale ignored fixture must be reported and corrected separately; it must not be
hidden or treated as a tracked product regression without investigation.

## Disposable PostgreSQL integration

CI starts a fresh PostgreSQL 17 service and runs:

```bash
PYTHONPATH=src:. python -m unittest discover \
  -s tests/integration/postgresql -v
```

The job creates synthetic Supabase-style API roles, provisions the private
schema and restricted runtime role, applies every migration, verifies a second
migration inspection, exercises representative reads and writes through
`clearspend_app`, checks API-role denial, and proves reviewed-import commit and
rollback. It uses synthetic credentials and data and must never point at the
private Supabase project.

This isolated service validates PostgreSQL SQL, transactions, migrations, and
permissions. Supabase TLS, Session-pooler behavior, and hosted-project settings
remain separate deployment checks.

## Frontend verification

Install locked dependencies and run the relevant checks from `frontend/`:

```bash
npm ci
npm test
npm run typecheck
npm run build
```

`npm test` runs both the framework-independent frontend model tests and the
Vitest/Vue Test Utils component-contract suite. Component tests cover shared
semantics, slots, events, attributes, ARIA relationships, density and dialog
behavior; Playwright remains responsible for complete workflows and focus
integration.

The production build writes generated assets to `dist/`. Review both source and
generated changes; do not hand-edit generated bundles.

The tracked dependency-free compatibility tests run from the repository root:

```bash
node --test tests/frontend/*.test.js
```

## Browser and visual tests

Install Chromium once, then run Playwright:

```bash
cd frontend
npx playwright install chromium
npm run test:e2e
```

Playwright starts the real local server on its dedicated test port and uses a
temporary synthetic SQLite database. It must never open or replace
`data/clearspend.db`.

Local macOS runs compare tracked screenshots. CI uses `npm run test:e2e:ci` to
run the same workflows without pixel comparisons that are unstable across
operating systems.

## Change-specific acceptance

| Change | Required emphasis |
| --- | --- |
| Pure financial rule | Boundary values, exclusions, precedence and deterministic evidence |
| Read query/report | Period/card/event scope, totals and empty coverage |
| Database write | Success, validation failure, rollback and preservation of unrelated state |
| Statement parser/import | Recognition, reconciliation, duplicate layers, pending rows, backup and failure injection |
| Schema migration | Empty/current/unsupported schema, verified backup, idempotence and rollback |
| Vue component | Loading, empty, error, keyboard and save states |
| Dashboard interaction | Desktop and narrow E2E; visual snapshot when appearance changes |
| Observation | Qualifying, suppressed, grouped, reviewed and later-period cases |

For changes that affect financial state, compare relevant before/after counts
and totals on a disposable copy. Production data is never the first test target.

## CI and merge acceptance

`.github/workflows/ci.yml` is the executable CI definition. It installs locked
Python and Node dependencies, runs tracked Python and compatibility tests,
checks Vue types and unit tests, builds production assets, runs Playwright, and
runs the isolated PostgreSQL integration job.

Before committing, also run `git diff --check`, inspect generated assets for
private data, stage only named paths, and run `.githooks/pre-commit`. Passing CI
does not replace review of financial semantics, privacy, or visual behavior.

Do not hard-code test totals in living documentation. The suite grows; command
success and CI configuration are the maintained evidence.
