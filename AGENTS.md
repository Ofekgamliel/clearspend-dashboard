# Repository instructions for coding agents

These rules apply to every automated or AI-assisted change in this repository.

## Read the relevant source of truth

- Git, commits, pushes, privacy checks: `GIT_WORKFLOW.md`
- Runtime boundaries, persistence, migrations: `docs/ARCHITECTURE.md`
- Current refactoring contracts and ownership: `docs/REFACTORING_BASELINE.md`
- Migration-runner design: `docs/DATABASE_MIGRATIONS.md`
- Imports, duplicates, merchants, categories: `docs/IMPORT_AND_MAPPING.md`
- Dates, installments, income, charts, totals: `docs/REPORTING_RULES.md`
- Observation eligibility, thresholds, merging, reviews: `docs/FINANCIAL_OBSERVATIONS.md`
- Layout and interaction behavior: `docs/UI_GUIDELINES.md`
- Running, backups, restore, and incident recovery: `docs/OPERATIONS_AND_RECOVERY.md`

Read every document relevant to the requested change before acting. If code,
documentation, and user instructions conflict, do not silently choose one;
surface the conflict and preserve user data while resolving it.

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
- Report backups, tests, files changed, commits created, and whether anything
  was pushed.
