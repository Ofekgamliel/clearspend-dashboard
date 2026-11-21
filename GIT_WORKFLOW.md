# ClearSpend Git workflow

This repository stores the ClearSpend application. Personal financial data stays
on the local computer and must never be committed or pushed to GitHub.

## What belongs in Git

Commit reusable application material only:

- Editable Vue source in `frontend/src/`
- Generated production frontend assets in `dist/`, rebuilt from reviewed source
- Application source in `src/`
- Generic, reusable utilities and synthetic integration tests explicitly
  allowed by `.gitignore`
- Dependency declarations and project documentation
- Privacy controls such as `.gitignore` and `.githooks/`

## What must remain local

Never commit or push:

- SQLite databases or database sidecar files
- Bank, card, salary, or income statements
- XLS, XLSX, Numbers, PDF, or CSV financial exports
- `data/`, `samples/`, `analysis/`, or `backups/`
- Merchant research or mappings derived from real transactions
- Review mockups containing real merchants, amounts, dates, or card suffixes
- Standalone design-review HTML files and screenshots, even when synthetic,
  unless they have deliberately become maintained production documentation
- Statement-derived tests or fixtures
- Local hosting/account metadata, virtual environments, or OS metadata
- Credentials, access tokens, SSH keys, passwords, or secrets
- Absolute local filesystem paths or company identity information

`.gitignore` blocks the known private locations and file types. The pre-commit
hook adds a second check, but neither replaces reviewing the staged diff.

Keep commits narrow enough to describe one responsibility and its verification.
Do not combine unrelated cleanup merely because the files are nearby.

## Safe workflow for a normal change

Run every command from the repository root.

1. Start from updated `main` and create a focused branch:

   ```bash
   git switch main
   git pull --ff-only origin main
   git switch -c feature/descriptive-name
   ```

   Do not mix personal and company remotes or identities. Do not work directly
   on `main` for an application change.

2. Inspect all changes:

   ```bash
   git status --short
   git diff
   ```

3. For frontend changes, edit `frontend/src/`, run the verified commands in
   `docs/TESTING.md`, and rebuild `dist/`. Never hand-edit a generated bundle.

4. Stage only named, reviewed files. Do not use `git add .` or `git add -A`:

   ```bash
   git add frontend/src/features/example/ExamplePanel.vue dist/index.html dist/assets/index-EXAMPLE.js
   ```

5. Review exactly what the commit would contain:

   ```bash
   git diff --cached --name-status
   git diff --cached
   git diff --cached --check
   ```

6. Confirm the repository identity and destination:

   ```bash
   git config --show-origin --get user.email
   git remote -v
   ```

   The email must come from this repository's `.git/config`. The remote must use
   the `github-personal` SSH alias and point to
   `Ofekgamliel/clearspend-dashboard`.

7. Run the applicable checks from `docs/TESTING.md`. Backend changes normally
   include at least the tracked synthetic suite:

   ```bash
   PYTHONPATH=src:. .venv/bin/python -m unittest discover -s tests/synthetic -v
   ```

   Also run the complete local regression suite when its private fixtures are
   available:

   ```bash
   PYTHONPATH=src:. .venv/bin/python -m unittest discover -s tests -v
   ```

   Only `tests/synthetic/`, `tests/integration/`, and `tests/frontend/` are
   committed. They contain synthetic data only. Statement-derived tests and
   fixtures elsewhere under `tests/` remain private and intentionally ignored.

8. Commit with a specific description:

   ```bash
   git commit -m "Describe the application change"
   ```

9. Inspect the final commit before pushing:

   ```bash
   git show --stat --oneline HEAD
   git status --short --branch
   ```

10. Push the focused branch only after the destination and staged content have
    been verified:

   ```bash
   git push -u origin feature/descriptive-name
   ```

11. Open a pull request against `main`. Record the behavior changed, privacy or
    data-safety implications, and verification performed. Merge only after the
    diff and required checks are reviewed. Delete the remote branch afterward
    only when the user requests or approves cleanup.

## Statement imports and database changes

Uploading a new statement through ClearSpend changes local ignored files, mainly
`data/clearspend.db` and local backups. It does not require a Git commit or push.
Only commit when the application code itself changes.

The same rule applies to income entries, merchant decisions, recurring rules,
event assignments, reimbursements, and observation reviews: they are database
state, not source-code changes.

When cloning the repository on another computer, Git provides a clean app with
no personal transactions. Transfer the database separately through an approved,
secure backup process; never use this GitHub repository as database storage.

## Hooks

The repository stores its hook in `.githooks/pre-commit`. Activate versioned
hooks after a fresh clone:

```bash
git config --local core.hooksPath .githooks
```

The hook rejects known private paths and extensions, company-email commit
identity, private-key material, common token formats, and absolute user paths.
Do not bypass it with `--no-verify`. If it produces a false positive, inspect
the staged content and update the rule transparently rather than skipping it.

## Correcting mistakes before a push

To unstage a file while preserving the local file:

```bash
git restore --staged path/to/file
```

To inspect the previous version:

```bash
git show HEAD:path/to/file
```

Do not use destructive commands such as `git reset --hard` to fix a staging
mistake. Restore from the local backup if necessary.

## If private data was committed

Stop before pushing. Do not merely delete the file in a second commit, because
the data remains in earlier history. Preserve a backup, remove the data from the
commit/history, run the privacy checks again, and only then push.

If private data or a credential was already pushed, stop immediately. Rotate
any exposed credential and remove the data from Git history before continuing.
