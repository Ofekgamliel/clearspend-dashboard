# Repository instructions for coding agents

These rules apply to every automated or AI-assisted change in this repository.

## Privacy boundary

- Treat all financial, income, statement, merchant-research, mapping, card,
  database, and backup content as private.
- Never stage, commit, push, quote, or copy private data into tracked files.
- Keep `data/`, `samples/`, `analysis/`, `backups/`, statement-derived tests,
  review mockups, and one-off research utilities local and ignored.
- Production frontend files must fetch financial data from the local API. Never
  embed real transactions, merchants, amounts, dates, income, or card suffixes.
- Never add credentials, tokens, private keys, local absolute paths, or company
  identity information to tracked files.

## Git operations

- Read `GIT_WORKFLOW.md` before changing Git state.
- Preserve the repository-local personal Git identity and the `github-personal`
  SSH remote. Do not change the user's global/company Git configuration.
- Never use `git add .` or `git add -A`. Stage explicit reviewed paths only.
- Before committing, inspect `git status --short`, `git diff`,
  `git diff --cached --name-status`, and `git diff --cached`.
- Run `.githooks/pre-commit` and the relevant tests before committing.
- Do not use `--no-verify` to bypass repository checks.
- Never push, force-push, rewrite published history, create releases, or change
  remote repository settings without explicit user authorization.
- Never run destructive recovery commands such as `git reset --hard` or remove
  private local data to clean the repository.
- Preserve unrelated user changes and ignored local data.

## Imports and local state

- Statement imports and merchant/category edits update the local database; they
  are not Git changes and must remain outside Git.
- A code change may alter schemas, importers, or UI behavior, but migrations
  must back up the local database before modifying it.
- Use synthetic data in any future tracked tests or examples. Real statement
  fixtures and derived assertions must stay ignored.

## Verification

- Run the local test suite when private fixtures are present:

  ```bash
  PYTHONPATH=src:. .venv/bin/python -m unittest discover -s tests -v
  ```

- Confirm the production frontend contains no embedded private data.
- Confirm ignored financial files remain ignored with `git check-ignore -v`.
- Report exactly which files were committed and whether anything was pushed.
