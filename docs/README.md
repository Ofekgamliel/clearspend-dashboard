# ClearSpend documentation

This directory separates current sources of truth from completed project
history. When documents overlap, the more specific current document owns its
subject. Archived plans never override current code or maintained guidance.

## Current development references

- [`ARCHITECTURE.md`](ARCHITECTURE.md) — runtime, module ownership, dependency
  rules, state ownership, and the workflow for changing the application.
- [`API_CONTRACTS.md`](API_CONTRACTS.md) — local HTTP endpoints, request scope,
  response ownership, mutation effects, and compatibility rules.
- [`TESTING.md`](TESTING.md) — verification layers, commands, data isolation,
  and change-specific acceptance checks.
- [`DATABASE_MIGRATIONS.md`](DATABASE_MIGRATIONS.md) — schema inspection,
  versioning, explicit migrations, backups, and future migration requirements.
- [`POSTGRES_MIGRATION_PLAN.md`](POSTGRES_MIGRATION_PLAN.md) — maintained record
  of the completed Supabase PostgreSQL port, dual-engine parity work, and
  maintenance-window authority cutover.
- [`POSTGRES_CUTOVER_RUNBOOK.md`](POSTGRES_CUTOVER_RUNBOOK.md) — controlled
  maintenance, verification, authority decision, and recovery procedure.
- [`PYTHON_39_COMPATIBILITY.md`](PYTHON_39_COMPATIBILITY.md) — concrete Python
  3.9 workarounds and the adjustments to revisit after a runtime upgrade.

## Financial and product behavior

- [`IMPORT_AND_MAPPING.md`](IMPORT_AND_MAPPING.md) — statement staging,
  duplicates, reconciliation, merchant decisions, and approved commit behavior.
- [`REPORTING_RULES.md`](REPORTING_RULES.md) — dates, reporting periods,
  installments, income, reimbursements, events, averages, and filtering.
- [`FINANCIAL_OBSERVATIONS.md`](FINANCIAL_OBSERVATIONS.md) — monthly findings,
  long-period patterns, grouping, evidence, and review policy.
- [`UI_GUIDELINES.md`](UI_GUIDELINES.md) — stable interaction patterns,
  accessibility, Vue state ownership, and visual-regression expectations.
- [`UI_COMPONENT_LIBRARY_EXECUTION_PLAN.md`](UI_COMPONENT_LIBRARY_EXECUTION_PLAN.md)
  — authoritative phased plan for the internal Vue component library.
- [`UI_COMPONENT_LIBRARY_INVENTORY.md`](UI_COMPONENT_LIBRARY_INVENTORY.md) —
  maintained control inventory and workflow-migration checklist.
- [`DASHBOARD_THEME_IMPLEMENTATION_PLAN.md`](DASHBOARD_THEME_IMPLEMENTATION_PLAN.md)
  — phased plan for selectable dashboard palettes across shared components,
  feature-owned styles, dialogs, and visualizations.

## Operations and repository safety

- [`OPERATIONS_AND_RECOVERY.md`](OPERATIONS_AND_RECOVERY.md) — starting the app,
  health checks, backups, restore, import verification, and portability.
- [`../GIT_WORKFLOW.md`](../GIT_WORKFLOW.md) — branches, staging, privacy checks,
  commits, pull requests, and handling accidental private data.
- [`../AGENTS.md`](../AGENTS.md) — concise mandatory instructions for coding
  agents working in the repository.

## Historical records

Files under [`archive/`](archive/) preserve completed refactoring decisions and
acceptance evidence. They are useful background, not living implementation
contracts:

- [`archive/REFACTORING_BASELINE.md`](archive/REFACTORING_BASELINE.md)
- [`archive/CLEARSPEND_REFACTORING_PLAN.md`](archive/CLEARSPEND_REFACTORING_PLAN.md)
- [`archive/VUE_PRODUCTION_PARITY_CHECKLIST.md`](archive/VUE_PRODUCTION_PARITY_CHECKLIST.md)

## Documentation maintenance

Update only the document that owns the changed behavior:

| Change | Review or update |
| --- | --- |
| Module ownership or dependency boundary | `ARCHITECTURE.md` |
| HTTP endpoint or exchanged semantics | `API_CONTRACTS.md` |
| Statement provider, staging, duplicates, mapping | `IMPORT_AND_MAPPING.md` |
| Financial calculation or reporting scope | `REPORTING_RULES.md` |
| Observation eligibility, evidence, grouping, review | `FINANCIAL_OBSERVATIONS.md` |
| Schema or migration behavior | `DATABASE_MIGRATIONS.md` |
| Python 3.9 compatibility workaround | `PYTHON_39_COMPATIBILITY.md` |
| Interaction or accessibility contract | `UI_GUIDELINES.md` |
| Startup, backup, restore, or rollback | `OPERATIONS_AND_RECOVERY.md` |
| Git, CI, generated assets, or privacy workflow | `GIT_WORKFLOW.md` |

Tests must reflect changed behavior. Unrelated documents do not need mechanical
updates merely to satisfy a checklist.
