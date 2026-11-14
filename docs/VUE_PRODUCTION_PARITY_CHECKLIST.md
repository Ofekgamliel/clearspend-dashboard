# Vue production parity checklist

This checklist tracks the work required before the Vue frontend on
`refactor/modular-architecture` can replace the current production frontend on
`main`.

`main` is the behavioral and visual reference. It uses the retired vanilla
JavaScript implementation in `dist/app.js`, including the large application
"god file". The goal is not to restore that architecture inside Vue. The goal
is to preserve the approved production behavior and appearance while keeping
the modular Python backend and Vue 3 + TypeScript frontend.

Do not merge the refactor branch until every merge gate at the end of this file
is complete.

## Confirmed foundations

- [x] Keep the modular Python backend and extracted domain/application modules.
- [x] Keep Vue source in `frontend/` and generated production assets in `dist/`.
- [x] Preserve the local SQLite database and private-data boundaries.
- [x] Confirm the common dashboard, category, transaction, recurring, and event
  read APIs return the same production data as `main` for representative views.
- [x] Confirm the Vue application builds and passes its current unit/type tests.
- [x] Treat the current Vue production cutover as incomplete until the remaining
  parity work and browser verification are finished.

## 1. Production shell and dashboard layout

- [x] Replace root preview-only naming and styling such as `preview-shell`,
  `preview-header`, and `preview-dashboard-grid` with production components and
  styles.
- [x] Restore the approved full-width desktop content area instead of limiting
  the primary dashboard to 1120px.
- [x] Match the production header height, logo size, control spacing, borders,
  shadows, and surrounding padding.
- [x] Match the compact approved `Income & spending` panel dimensions and
  alignment.
- [x] Restore the production two-column analytical layout:
  - Purchase activity and Spending by card on the left.
  - The tall Categories panel on the right.
  - Category height aligned with the combined left-side panels.
- [x] Remove the unused blank area below Spending by card.
- [x] Keep Financial observations, Recurring & commitments, Projects & events,
  and Recent transactions aligned to the same main content width.
- [x] Fix Financial observations extending outside the primary content wrapper.
- [x] Match approved typography sizes and weights; remove preview-scale 7–9px
  text where it makes production content difficult to read.
- [x] Restore the approved page background rather than the preview radial
  gradient.
- [x] Restore the footer showing last-import state and local-database status.
- [x] Verify layout at the production desktop width and at supported narrow
  viewport widths.

## 2. Header filters and management navigation

- [x] Replace the native month `<select>` with the approved year/month grid
  picker.
- [x] Show which historical months contain imported data.
- [x] Restore previous/next-year navigation and the `Latest month` action.
- [x] Replace the native card `<select>` with the approved custom card picker.
- [x] Keep the card popover anchored below its control and constrained to the
  control width unless content requires more room.
- [x] Match the selected-value typography across period, month, and card
  controls.
- [x] Restore the approved icon-only data-management control and its accessible
  label instead of the large `Manage data` text button.
- [x] Keep the three approved top-level management destinations:
  - Import statements.
  - Import history.
  - Merchants.
- [x] Keep Needs review and recurring-rule management inside the Merchants
  workspace instead of duplicating them as top-level menu destinations.
- [x] Close the management menu when clicking outside it or pressing Escape.
- [x] Preserve one shared period/month/card state across every dashboard panel
  and detail view.

## 3. Money, dates, labels, and shared formatting

- [x] Restore consistent left-side shekel formatting such as `₪1,234.56` and
  prevent bidirectional text from rendering `1,234.56₪`.
- [x] Verify negative charges, refunds, original-currency values, percentages,
  dates, and month labels against `main`.
- [x] Verify money formatting inside panels, tooltips, tables, modals, event
  summaries, recurring views, imports, and observation evidence.
- [x] Keep Hebrew/English merchant and category strings readable without bidi
  reordering.

## 4. Categories and card spending

- [x] Remove the visible `FIRST MIGRATED FEATURE` development label.
- [x] Restore the approved Categories panel size, donut size, list proportions,
  scrolling, and column alignment.
- [x] Restore the `View details` category overview action and its complete
  period-aware category list.
- [x] Restore donut hover/focus details showing category, amount, and share.
- [x] Keep `All spending` and `Routine only` behavior identical to `main`.
- [x] Preserve previous-month comparison badges and unavailable/new states.
- [x] Keep category-row clicks opening grouped category transactions.
- [x] Verify grouped and individual category transaction modes, sorting, row
  expansion, source fields, category correction, and event labels.
- [x] Restore the Spending by card help action and its explanatory feedback.
- [x] Verify selecting a card from the card panel updates the shared dashboard
  filter.

## 5. Purchase activity and chart interactions

- [x] Match the production chart dimensions, axes, labels, spacing, and daily
  category stacks.
- [x] Match monthly, Latest year, and All time chart behavior.
- [x] Restore pointer-positioned chart tooltips rather than showing a fixed
  tooltip above the chart.
- [x] Verify category amounts, refunds, cumulative purchase value, income bars,
  and hidden-income behavior.
- [x] Verify installment collapsing and purchase-date versus reporting-month
  rules remain presentation-compatible with `main`.

## 6. Staged statement import — merge blocker

- [x] Preserve the five reviewed stages: Files, Checks, Merchants, Reconcile,
  and Approve.
- [x] Remove the unwanted visible `Data management` kicker from the modal.
- [x] Restore the merchant `Context` column with provider and transaction date
  range.
- [x] Restore the reviewed searchable display-name combobox.
- [x] Show matching identity aliases, transaction counts, and category context.
- [x] Distinguish unanimous and mixed-category display identities.
- [x] Show a correctly sized option to create a new display identity from the
  original statement merchant name.
- [x] Position the display-name suggestion menu above other panels and open it
  upward when there is insufficient space below.
- [x] Preserve automatic high-confidence suggestions for resolution, display
  identity, unanimous category, and permanent exact-name scope.
- [x] Keep every suggestion editable until final approval.
- [x] Match dense-table select typography and arrow inset.
- [x] Restore complete exact-duplicate evidence, including matched database
  identity/card context where available.
- [x] Restore complete possible-duplicate evidence, including existing database
  transaction IDs and billing context.
- [x] Require a decision for every possible duplicate before continuing.
- [x] Show coverage warnings, pending counts, outside-cycle counts, and
  statement-period provenance.
- [x] Reconcile the correct provider total and clearly distinguish scheduled,
  pending, immediate, and outside-cycle rows.
- [x] Restore the detailed approval summary:
  - Permanent merchant decisions.
  - Deferred/Needs review decisions.
  - Excluded merchants/rows.
  - Known and reviewed merchants.
  - Exact and reviewed duplicates.
  - Manual reconciliation confirmations.
- [x] Show every transaction that will be inserted in the final preview.
- [x] Show pending transactions in a separate `Pending—not imported` preview.
- [x] Confirm the only database-writing action is the final approved commit.
- [x] Verify a backup is created immediately before the commit.
- [x] Test analyze, cancel, replace staged files, approve, successful commit,
  validation errors, and server errors against a disposable database copy.

## 7. Merchant and mapping management

- [x] Remove the unwanted visible `Data management` kicker.
- [x] Preserve the Needs review/mapping queue as a direct filter inside the
  Merchants workspace.
- [x] Restore merchant category and recurring-status filters.
- [x] Restore the useful merchant summary metrics from `main`.
- [x] Preserve search across display names and every original alias.
- [x] Preserve per-alias permanent categories inside a shared display identity.
- [x] Keep display-name editing independent from alias category editing.
- [x] Restore recurring profile management inside the merchant workflow, or
  provide an equally direct link without losing context.
- [x] Show and save the exact aliases included in a recurring profile.
- [x] Keep impact review before applying display-name or category changes.
- [x] Keep recurring removal confirmation separate from ended lifecycle.
- [x] Verify saved changes update the database and refresh affected panels.
- [x] Verify transaction-specific category overrides remain unchanged by a
  permanent merchant edit.

## 8. Transactions and transaction-specific actions

- [x] Match the production Recent transactions table appearance without adding
  event badges to the compact dashboard rows.
- [x] Preserve complete-history substring search within the selected period and
  card rather than searching only rendered rows.
- [x] Preserve grouped and individual category transaction modes.
- [x] Preserve default transaction-date descending order and sortable columns.
- [x] Preserve all source columns in individual/expanded transaction rows.
- [x] Keep original statement merchant descriptions visible.
- [x] Keep the compact category edit affordance on hover and keyboard focus.
- [x] Keep event labels immediately beside categories only in individual rows.
- [x] Keep the reimbursement action as a compact pinned icon-only column.
- [x] Verify category corrections, reimbursement add/edit/remove, event
  assignment/removal, refresh behavior, errors, and confirmation flows against
  a disposable database copy.
- [x] Match transaction modal centering, dimensions, table scrolling, sticky
  headers, and action-column positioning.

## 9. Recurring and commitments

- [x] Match the production panel and modal spacing, table typography, dropdown
  sizes, arrow inset, and selected-row colors.
- [x] Preserve separate Recurring & scheduled and Commitments lists.
- [x] Preserve scrolling when more than the visible rows exist.
- [x] Preserve sortable columns in both tabs.
- [x] Preserve actual billing history for the exact aliases included in each
  recurring profile.
- [x] Preserve Type, Cadence, Lifecycle, optional end month, and explicit save
  behavior.
- [x] Preserve recurring removal/addition management and confirmation.
- [x] Verify recurring billed and commitment totals remain separate.
- [x] Verify Manage data → Merchants exposes recurring membership, type,
  cadence, and lifecycle controls without a duplicate Recurring rules menu
  destination.

## 10. Projects and events

- [x] Match the approved event cards, icons, Hebrew names, amount placement, and
  completed-state presentation.
- [x] Preserve the collapsed `No active projects` row and New event action.
- [x] Preserve tabless event details and the compact separate Edit event modal.
- [x] Preserve editable name, type, dates, budget, and status without a notes
  field.
- [x] Preserve business-trip destination and blue business-trip styling.
- [x] Preserve automatic destination grouping in Latest year and All time while
  keeping individual trips in month view.
- [x] Preserve the grouped summary, centered trip list, trip drill-down, and
  clean back-arrow interaction.
- [x] Preserve category filtering of exact event transaction membership.
- [x] Verify event dates affect period visibility only and never change exact
  transaction membership.
- [x] Verify create, edit, assignment, unassignment, and cancelled-event behavior
  against a disposable database copy.

## 11. Financial observations

- [x] Match the approved monthly versus Latest year/All time observation
  presentation and terminology.
- [x] Preserve grouped cards, merchant/finding summaries, comparison periods,
  evidence rows, and related-activity navigation.
- [x] Preserve compact review actions only for explicitly reviewable finding
  types; factual findings must have no dismissal action.
- [x] Preserve per-finding resolution inside grouped cards.
- [x] Preserve the external temporary Undo notification after a resolution.
- [x] Preserve collapsed empty-state behavior for no monthly observations or no
  lasting patterns.
- [x] Match icon, color, title, body, modal, and evidence styling from `main`.
- [x] Verify reviewed findings, future reappearance rules, navigation, income
  privacy, and error states against representative synthetic cases.

## 12. Income privacy and accessibility

- [x] Verify the eye-only income control matches production and retains its
  accessible name.
- [x] When hidden, remove sensitive values from visible text, tooltips, chart
  labels, and the accessibility tree; do not rely only on CSS blur.
- [x] Verify the visibility preference survives reloads without briefly
  exposing income.
- [x] Give every icon-only action an accessible label and tooltip where useful.
- [x] Make hover-only actions available on keyboard focus.
- [x] Expose active sort direction through `aria-sort` or an equivalent state.
- [x] Ensure warning, selection, and status meaning is not communicated by color
  alone.
- [x] Verify focus trapping/order, Escape, backdrop close, and focus restoration
  for every modal.

## 13. Runtime and stale-server protection

- [x] Document and verify that changing between `main` and the refactor requires
  restarting the Python server, because frontend and backend API versions must
  match.
- [x] Add a frontend/backend compatibility or build identifier so a stale server
  produces a clear error instead of silently missing endpoints.
- [x] Show a useful error and retry action when a required API endpoint is not
  available.
- [x] Verify `/api/health` before browser acceptance tests.

## 14. Automated parity and regression coverage

- [x] Add browser end-to-end tests for period/month/card filtering.
- [x] Add browser tests for category drill-down, transaction search, sorting,
  category correction, reimbursement, and event assignment.
- [x] Add browser tests for merchant and recurring management.
- [x] Add browser tests for all five import stages using synthetic statements
  and a disposable database.
- [x] Add screenshot/visual-regression coverage for the main dashboard at
  desktop and narrow widths.
- [x] Add screenshot coverage for the transaction, import, merchant, recurring,
  observation, event-detail, event-edit, and event-create modals.
- [x] Add an automated check preventing preview/debug labels from appearing in
  the production build.
- [x] Add currency/bidi presentation tests.
- [x] Keep backend contract, calculation, duplicate, observation, and migration
  tests passing.

## Merge gates

- [x] Every checklist section above is complete or explicitly reviewed and
  accepted as an intentional product change.
- [x] The full synthetic Python suite passes.
- [x] The complete local suite passes when private fixtures are available.
- [x] Frontend unit tests, type checking, production build, and browser E2E tests
  pass.
- [x] Representative API responses and dashboard totals match `main` against a
  copied production database.
- [x] Every write workflow passes against a disposable database and the live
  database remains untouched during testing.
- [x] Desktop and narrow-width visual comparisons are reviewed.
- [x] Generated `dist/` contains no private data, preview labels, or stale
  development assets.
- [x] Git privacy checks pass and only explicitly reviewed files are staged.
- [ ] The branch is reviewed before merging; passing CI alone is not treated as
  proof of UI parity.
