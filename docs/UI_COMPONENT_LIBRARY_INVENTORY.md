# UI component library migration inventory

## Purpose and maintenance

This is the implementation checklist for
[`UI_COMPONENT_LIBRARY_EXECUTION_PLAN.md`](UI_COMPONENT_LIBRARY_EXECUTION_PLAN.md).
It records existing production controls, their semantics and their migration
disposition. Update the relevant row in the same change that migrates a
workflow or removes a selector.

Status values are `pilot`, `planned`, `deferred`, `exception`, and `migrated`.
An item remains feature-owned while its semantics are unresolved. Shared
components require at least two independent uses demonstrated here or in
implemented consumers.

## Inventory

| Existing control | File and feature owner | Current consumers | Native/ARIA semantics and keyboard behavior | Density | Existing selectors | Target or exception | Required tests | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Primary form action | Events, Transactions, Merchants, Imports | Create/save event, save correction/adjustment, apply merchant changes, continue/import | Native submit or button; Enter follows form semantics; disabled during invalid/loading states | Regular | `.primary`, feature footer rules | `UiButton` primary; feature retains submit/save logic | Default type, submit type, disabled, busy, accessible text; workflow E2E | pilot |
| Secondary form action | Events, Transactions, Merchants | Cancel/close editors, review merchant impact | Native button; disabled where appropriate | Regular | `.secondary`, feature footer rules | `UiButton` secondary | Click emission, disabled, focus-visible; workflow E2E | pilot |
| Destructive action | Merchant recurring editor, transaction adjustment | Remove recurring status or adjustment | Native button; confirmation remains feature-owned | Regular | `.danger`, `.remove` | `UiButton` danger after confirmation semantics are preserved | Danger presentation, disabled/busy; removal E2E | planned |
| Dialog close action | Categories, Events, Observations, Recurring, Transactions, Merchants, Imports | Every large and compact overlay | Native icon-only button with accessible label; Escape is handled by feature today | Icon regular/compact | `.transactions-modal-close`, `.event-modal-close-preview`, `.observation-modal-close-preview`, `.recurring-modal-close`, `.transaction-editor-close` | `UiIconButton` composed by `UiDialog`; label required | Accessible name, focus-visible, click; dialog keyboard E2E | pilot |
| Other icon action | Income, Cards, transaction tables, dashboard header | Privacy, help, edit/expand, management | Native icon-only button; labels vary; tooltip behavior is inconsistent | Icon regular/compact | Feature-specific button selectors | `UiIconButton` only after each semantic treatment is demonstrated | Label, tooltip decision, hover/focus parity | planned |
| Retry action | App, filters, panels and modal loaders | Runtime, filters, categories, events, recurring, observations, transactions, merchants, audit | Native button in alert/status context | Regular | State-local button rules | `UiButton` secondary or feature-owned compact retry after visual comparison | Alert association, click, focus | planned |
| Link-like detail action | Categories, Transactions, Recurring | Open category, transaction and recurring detail views | Native action button, not navigation | Regular/text | `.category-view-details`, `.transactions-view-all`, panel-specific rules | Possible `UiButton` ghost/link-like action only if one repeated contract is proven | Native button semantics, focus, disabled | deferred |
| Sort-header action | Transaction and recurring tables | Sort columns | Native button inside `th`; parent exposes `aria-sort` | Dense | Table-specific `th button` rules | Keep feature-owned until repeated table primitive is justified | Sort state/direction and keyboard | deferred |
| Row/card action | Categories, Cards, Events, Observations, Recurring | Open details or select a row/card | Native button, or keyboard-enabled row in recurring detail | Content-specific | Feature card/row selectors | Feature-owned; visual similarity does not imply one behavior | Accessible name/state, Enter/Space where applicable | exception |
| Standard dashboard panel frame | Income, Metrics, Trend, Cards, Categories, Recurring, Events, Observations, Transactions | Dashboard panels | Section/article semantics vary; headings are feature-owned | Standard; Income compact hierarchy | Panel selectors in `style.css` and feature CSS | `UiPanel` after read-only panel pilot | Heading level/label, slots, responsive visual E2E | planned |
| Large read/detail dialog | Categories, Events detail, Observations, Recurring, Transactions, Merchants, Import audit/manager | Cross-feature overlays | Custom teleported `role="dialog"`, `aria-modal`, labelled title, `v-modal-focus`; backdrop behavior varies | Large | Feature backdrop/modal selectors | `UiDialog` after native-versus-custom decision | Initial/trapped/restored focus, Escape/backdrop reason, nesting, scroll/inertness | planned |
| Compact create/edit dialog | Events create/edit, transaction category/adjustment | Focused editing workflows | Custom teleported `role="dialog"`, labelled title, focus directive | Compact | `.event-create-modal-preview`, `.transaction-category-editor`, `.transaction-adjustment-editor` | `UiDialog` compact; event create/edit is first pilot | Dialog contract tests plus event create/edit Playwright and snapshots | pilot |
| Regular labelled input | Events, transaction editors, merchant recurring | Text, date, month and numeric fields | Native input inside label; errors are currently form-level | Regular | Feature label/input rules | `UiField` + `UiInput` | ID/label/help/error association, attributes, `v-model` | pilot |
| Regular labelled select | Events, transaction category, merchant recurring | Type, status, category, cadence, lifecycle | Native select inside label | Regular | Feature label/select rules | `UiField` + `UiSelect` | Label/error association, options, disabled, `v-model` | pilot |
| Search input | Transaction browser, merchant management | Search/filter local result sets | Native search/text input; some use visually hidden or absent label | Regular | `.transactions-search`, merchant filter rules | Compose shared input only after accessible naming contract is resolved | Search semantics, accessible name, clear behavior | planned |
| Dense table select | Recurring tables, import decisions | Inline type/cadence and review decisions | Native select; often `aria-label` rather than visible label | Dense | `.recurring-inline-select-preview`, import table rules | `UiSelect` dense after regular field pilot | Accessible name, disabled, keyboard, stacking | planned |
| Checkbox | Import reconciliation, recurring alias selection | Explicit review/inclusion decisions | Native checkbox in label | Dense/regular | Feature-specific | Keep native and feature-owned until repeated frame behavior is proven | Checked/disabled and label | deferred |
| Radio choice cards | Transaction adjustment | Full versus partial reimbursement | Native radio group represented by labelled cards | Regular | `.transaction-adjustment-kinds` | Feature-owned; financial choice-card presentation | Arrow/selection behavior and labels | exception |
| Reporting-period segmented choice | Dashboard filters | Month/year/all reporting scope | `role="group"` with native buttons and `aria-pressed` | Regular | `.period-tabs` | Pressed-button group; candidate explicit selection primitive | Selected state, keyboard tab order, focus | planned |
| Category/transaction segmented choice | Categories, Transaction browser | Spending scope and grouped/individual presentation | `role="group"`, native buttons, `aria-pressed` | Compact/regular | `.scope-toggle`, `.transaction-view-toggle` | Candidate pressed-button selection primitive after density comparison | Selected state and keyboard | planned |
| Recurring modal toolbar | Recurring | Period and content view | Native buttons without complete selected-state semantics | Compact | `.recurring-modal-toolbar` | Defer until semantics are corrected; tabs only if panels satisfy tab contract | Role/state/keyboard tests | deferred |
| Management menu | Management | Three management destinations | Button with `aria-haspopup="menu"`; `role="menu/menuitem"` but no complete arrow-key contract | Header | `.app-manage-*` | Feature-owned disclosure unless true menu keyboard behavior is added | Escape, outside click, focus return, arrow keys if menu | deferred |
| Month picker overlay | Filters | Reporting month selection | Trigger advertises dialog; labelled `role="dialog"`; grid of native buttons | Header/popover | `.month-picker-*` | Feature-owned; assess dismissable-layer reuse | Focus entry/return, Escape, outside click, narrow viewport | deferred |
| Card picker overlay | Filters | Card selection | Trigger advertises listbox; popup uses buttons with option roles | Header/popover | `.card-picker-*` | Resolve listbox keyboard contract before sharing | Arrow/selection/Escape/outside click | deferred |
| Card help disclosure | Cards | Explanatory help | Button toggles status popover | Panel popover | `.cards-help-*` | Feature-owned disclosure; no generic overlay yet | Expanded state, focus/outside dismissal | deferred |
| Identity combobox | Imports | Merchant identity review | Input/button interaction with teleported/listbox-like menu behavior | Dense | `.identity-combobox-*` | Feature-owned and migrated with staged import last | Full keyboard, focus, positioning and import E2E | deferred |
| Compact status badge | Metrics, Categories, Transactions, Recurring, Imports | Metadata, comparisons, categories, recurring state, staged state | Text elements; meaning sometimes supplemented by text/title | Compact | `.metric-pill`, `.comparison-badge`, `.transaction-category-pill`, `.recurring-status-pill`, `.import-staged-badge` | `UiBadge` only for repeated semantic status; category colors remain data encoding | Text alternative, semantic variant, contrast | planned |
| Inline alert/status | Runtime, panels, dialogs, import | Loading, error, warning and staged information | `role="alert"` or `status`; some plain state containers | Inline | `.error-state`, `.panel-state`, feature callouts | Inventory semantics before `UiInlineNotice`; validation remains near fields/workflows | Live-region role and announcement behavior | deferred |
| Transient result/undo notice | Events, Transactions, Recurring, Observations | Save result, error, dismissal and undo | Teleported `status`/`alert` with optional action | Toast | `.event-save-notice-preview`, `.transaction-save-notice`, `.recurring-save-notice-preview`, observation notice rules | Separate result and undo contracts; do not force one toast API prematurely | Politeness, focus, dismissal, timeout, undo E2E | planned |

## First pilot decision

The first vertical pilot is the Events create/edit workflow in
`frontend/src/features/events/EventsPanel.vue`.

It is selected because:

- create and edit are bounded forms with established feature ownership;
- buttons, close actions, dialog frames, labels, inputs and selects have
  independent consumers in transaction and merchant workflows;
- the workflow already has write-path and visual Playwright coverage;
- it does not contain nested dialogs, dense tables or import behavior;
- event validation, API calls and persisted state can remain unchanged.

The pilot may introduce only `UiButton`, `UiIconButton`, `UiDialog`, `UiField`,
`UiInput` and `UiSelect`. It must not migrate the event detail dialog, event
cards or unrelated controls in the same slice.

## Decisions and deferrals

- `UiDialog` retains a custom teleported `role="dialog"` implementation. The
  application already has a tested nested-overlay focus stack and exact modal
  presentation; changing to native `dialog` would combine the component pilot
  with a separate browser/top-layer and nested-modal migration. Reconsider only
  through a focused accessibility and browser-behavior comparison.
- Keep overlay mechanics private to their owner until two independent overlays
  demonstrate the same contract.
- Do not implement a generic segmented control until each consumer's selection
  semantics are corrected and classified.
- Do not bring the separate dashboard-theme branch into this branch. Compare or
  cherry-pick it only through a separately reviewed decision.

## Pilot progress

Event create/edit is migrated to `UiButton`, `UiIconButton`, `UiDialog`,
`UiField`, `UiInput` and `UiSelect`. The slice preserves Event-owned forms,
validation, API calls, saving state and notices. Its former create/edit frame,
field and footer selectors were removed; the Event detail dialog and cards were
not migrated.

Verification for this slice includes isolated component contracts, existing
frontend unit tests, type checking, production build/gallery-exclusion check,
the Event write workflow and unchanged event modal snapshots. The table rows
remain `pilot` or `planned` until their remaining listed consumers migrate.
