# Repository instructions for coding agents

These rules apply to every automated or AI-assisted change in this repository.

## Read the relevant source of truth

- Git, commits, pushes, privacy checks: `GIT_WORKFLOW.md`
- Documentation map and ownership: `docs/README.md`
- Runtime boundaries, module ownership, dependencies: `docs/ARCHITECTURE.md`
- HTTP request/response semantics: `docs/API_CONTRACTS.md`
- Migration-runner design: `docs/DATABASE_MIGRATIONS.md`
- Imports, duplicates, merchants, categories: `docs/IMPORT_AND_MAPPING.md`
- Dates, installments, income, charts, totals: `docs/REPORTING_RULES.md`
- Observation eligibility, thresholds, merging, reviews: `docs/FINANCIAL_OBSERVATIONS.md`
- Layout and interaction behavior: `docs/UI_GUIDELINES.md`
- Running, backups, restore, and incident recovery: `docs/OPERATIONS_AND_RECOVERY.md`
- Test layers and change-specific verification: `docs/TESTING.md`

Read every document relevant to the requested change before acting. If code,
documentation, and user instructions conflict, do not silently choose one;
surface the conflict and preserve user data while resolving it.

Historical files under `docs/archive/` are background only. They never override
current architecture, API, domain, or operational documentation.

## Architecture and implementation

- Follow the Vue 3 + TypeScript + Vite frontend architecture. Author production
  UI in `frontend/src/`; never add hand-written features to generated `dist/`.
- Identify the existing feature owner before adding a shared helper, component,
  composable, API path, query, service, parser, or migration.
- Keep browser transport and TypeScript contracts synchronized with backend
  endpoints. TypeScript contracts do not replace server validation.
- Keep authoritative financial calculations and qualifications in Python. Vue
  may own transient interaction state and presentation transforms.
- Use component-local state by default, feature composables when behavior is
  genuinely shared, and global state only after a concrete cross-feature need.
- Update `ARCHITECTURE.md` when responsibility or dependency boundaries change;
  update the owning domain document only when its behavior changes.

## Non-negotiable privacy boundary

- Treat all financial, income, statement, merchant-research, mapping, card,
  database, and backup content as private.
- Never stage, commit, push, quote, or copy private data into tracked files.
- Keep `data/`, `samples/`, `analysis/`, `backups/`, statement-derived tests,
  review mockups, and one-off research utilities local and ignored.
- Production frontend files fetch financial data from the local API. Never embed
  real transactions, merchants, amounts, dates, income, or card suffixes.
- Never add credentials, keys, tokens, absolute local paths, or company identity
  information to tracked files.
- Use synthetic data in future tracked tests, documentation, and examples.

## Non-negotiable data behavior

- Back up the database before migrations, bulk mapping/category changes,
  duplicate repairs, or approved imports.
- Check approved local merchant mappings before provider evidence or authorized
  online research. Never overwrite a reviewed mapping automatically.
- Keep merchant category, display identity, and transaction-specific overrides
  independent. One display identity may legitimately contain several categories.
- Preserve purchase date separately from reporting month and preserve provider
  billing/installment evidence.
- Maintain all three duplicate layers: exact file, semantic statement, and
  transaction identity.
- Stage and review an import before writing it to the live transaction set.
- Preserve observation thresholds, exclusions, precedence, and review identity.
  A UI-only change must not silently alter what qualifies as a finding.
- Income privacy is a data-exposure boundary, not merely a blur effect. Hidden
  values must not remain available in visible text, tooltips, charts, or the
  accessibility tree.

## Git operations

- Preserve the repository-local personal identity and `github-personal` remote.
  Do not change the user's global/company Git configuration.
- Never use `git add .` or `git add -A`; stage explicit reviewed paths only.
- Inspect unstaged and staged diffs before committing.
- Run `.githooks/pre-commit` and relevant tests. Never use `--no-verify`.
- Never push, force-push, rewrite published history, create releases, or change
  remote settings without explicit user authorization.
- Never use destructive recovery commands or delete private local data merely to
  clean Git state. Preserve unrelated user changes.

## Verification and reporting

- Run the tracked synthetic suite for every applicable code change:

  ```bash
  PYTHONPATH=src:. .venv/bin/python -m unittest discover -s tests/synthetic -v
  ```

- Also run the complete local suite when private fixtures are present:

  ```bash
  PYTHONPATH=src:. .venv/bin/python -m unittest discover -s tests -v
  ```

- Confirm ignored financial files remain ignored and production assets contain
  no embedded private data.
- Verify before/after counts and totals for data-model or reporting changes.
- For observation changes, verify representative qualifying, suppressed,
  grouped, reviewed, and future-period cases.
- For frontend changes, run applicable Vue tests, type checking, production
  build, and Playwright workflows from `docs/TESTING.md`.
- Report backups, tests, files changed, commits created, and whether anything
  was pushed.
