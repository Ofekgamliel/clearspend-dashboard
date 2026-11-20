# Dashboard theme implementation plan

## Status

Completed and merged through PR #7 from `feature/dashboard-theme-system`.
This archived plan records the implementation requirements and acceptance
criteria. Current behavior and maintenance guidance live in
[`../DASHBOARD_THEMES.md`](../DASHBOARD_THEMES.md).

## Objective

Add user-selectable dashboard color schemes that consistently cover the
application shell, dashboard panels, shared controls, dialogs, feature-owned
content, and data visualizations without returning feature selectors to the
global stylesheet.

The implementation must preserve existing layout, financial behavior,
accessibility, income privacy, and feature ownership boundaries.

## Non-goals

- Do not redesign dashboard structure or navigation as part of the theme work.
- Do not change financial calculations, API contracts, persisted financial
  data, observation qualification, or reporting scope.
- Do not introduce a general-purpose design-system dependency.
- Do not merge the old theme branch or copy its monolithic global override
  block into the current application.
- Do not require a backend setting or database migration. Theme preference is
  browser-local presentation state.
- Do not communicate category, warning, success, or selection state by color
  alone.

## Standards baseline

The implementation follows these external baselines where they apply:

- [WCAG 2.2](https://www.w3.org/TR/WCAG22/) Level AA for text contrast,
  non-text contrast, visible focus, and non-color communication;
- [CSS Color Adjustment Module Level 1](https://www.w3.org/TR/css-color-adjust-1/)
  for `color-scheme` and forced-color behavior; and
- the stable [Design Tokens Format Module
  2025.10](https://www.designtokens.org/tr/2025.10/format/) as industry
  guidance for token vocabulary, aliases, grouping, and compatibility. The
  implementation remains CSS-native and does not need to adopt the DTCG JSON
  interchange format.

## Existing architectural boundaries

The implementation follows the maintained boundaries in `ARCHITECTURE.md` and
`UI_GUIDELINES.md`:

| Area | Owner | Responsibility |
| --- | --- | --- |
| Semantic color contract | `frontend/src/shared/theme/` | Stable purpose-based tokens used across features and components |
| Shared controls and frames | `frontend/src/shared/ui/` | Buttons, inputs, selects, fields, panels, dialogs, and their states |
| Cross-feature chart encoding | `frontend/src/shared/visualization/` | Reusable chart-slot references and non-financial display encoding |
| Theme picker workflow | `frontend/src/features/theme/` | Picker presentation, interaction, and browser-local preference behavior |
| Feature presentation | `frontend/src/features/<feature>/` | Feature-specific surfaces, states, and local semantic aliases |
| Application composition | `frontend/src/App.vue` | Picker placement and explicit integration with the dashboard shell |
| Application shell | `frontend/src/style.css` | Page background, header, filters, footer, and remaining dashboard-owned layout |
| Generated production assets | `dist/` | Build output only; never hand-edited |

Shared modules must not import feature modules. Features may consume shared
theme, visualization, and UI contracts.

## Theme architecture

### 1. Semantic tokens

Expand `frontend/src/shared/theme/tokens.css` into the stable contract consumed
by the application. Components and features should request a visual purpose,
not a literal palette value.

The contract should cover at least:

```css
/* Foundation */
--ui-page-bg;
--ui-surface;
--ui-surface-muted;
--ui-surface-raised;
--ui-surface-hover;

/* Content */
--ui-text;
--ui-heading;
--ui-label;
--ui-muted;
--ui-subtle;
--ui-on-primary;

/* Structure */
--ui-border;
--ui-divider;
--ui-panel-border;
--ui-panel-shadow;
--ui-dialog-border;
--ui-dialog-shadow;
--ui-overlay;
--ui-overlay-nested;

/* Interaction */
--ui-primary;
--ui-primary-hover;
--ui-accent-soft;
--ui-accent-border;
--ui-accent-text;
--ui-focus;
--ui-focus-border;
--ui-focus-soft;

/* Semantic status */
--ui-success;
--ui-success-soft;
--ui-warning;
--ui-warning-soft;
--ui-danger;
--ui-danger-soft;
--ui-danger-border;

/* Data visualization */
--ui-chart-1;
--ui-chart-2;
--ui-chart-3;
--ui-chart-4;
--ui-chart-5;
--ui-chart-6;
--ui-chart-7;
--ui-chart-8;
--ui-chart-9;
--ui-chart-empty;
```

The exact final list should be derived from a hardcoded-color inventory. Avoid
adding aliases that differ only by feature name when an existing semantic role
is sufficient.

### 2. Palette definitions

Add `frontend/src/shared/theme/palettes.css`. The default `:root` contract stays
compatible with the current approved dashboard. Each selectable palette
overrides the complete `--theme-*` foundation set under a root data attribute;
the stable `--ui-*` semantic contract aliases those foundation values:

```css
:root[data-clearspend-theme="graphite"] {
  --theme-page-bg: #111315;
  --theme-surface: #1b1e21;
  --theme-heading: #f0f2f2;
  --theme-primary: #e0a53b;
  /* Complete foundation and chart token set. */
}
```

Every palette must define the complete required contract. A palette must not
contain selectors for Events, Merchants, Recurring, or any other feature.

Every registered palette must declare whether it is light or dark. Applying a
palette must also apply the matching inherited `color-scheme` value so native
form controls, scrollbars, carets, and browser-provided UI use the correct
scheme. `frontend/index.html` must advertise support for both light and dark
schemes before styles load, while the validated stored selection is applied
before the Vue application becomes visible.

The earlier `feature/dashboard-theme-layout` branch may supply candidate color
values and names. Values must be reviewed against the current UI rather than
copied mechanically.

### Token and theme lifecycle

The semantic token names and persisted theme identifiers form compatibility
contracts:

- Rename a consumed token through a temporary alias, migrate all known
  consumers, and remove the alias only after ownership tests prove the old name
  is unused.
- Record deprecated tokens and their replacement in the maintained theme
  inventory or implementation documentation.
- Do not change an existing theme identifier merely because its display name or
  palette values change.
- Version the browser-storage payload. A known retired identifier should map to
  an explicit successor when one exists; unknown, malformed, or unsupported
  values must fall back deterministically to the default.
- Test registry additions, identifier migrations, aliases, and fallback
  behavior. Never leave a partially defined palette to inherit accidental
  values from a previously selected theme.

### 3. Shared component consumption

Shared components should consume only semantic tokens for their visual states:

- `UiButton`: primary, secondary, soft-accent, danger, ghost, hover, focus, and
  disabled treatments.
- `UiInput` and `UiSelect`: surface, text, border, focus, invalid, and disabled
  treatments.
- `UiField`: label, help, and error content.
- `UiDialog`: surface, header/footer, divider, overlay, nested overlay, and
  shadow.
- `UiPanel`: surface, border, and shadow.
- `UiIconButton`: inherited semantic variants and focus treatment.

Theme selection belongs on `document.documentElement`. Teleported dialogs will
therefore inherit the same contract without modal-specific theme plumbing.

Features must not pass arbitrary palette colors or dimensions into shared
components. A feature may select a documented semantic variant.

### 4. Feature-owned presentation

Each feature stylesheet converts its remaining literal presentation colors to
shared tokens or feature-local semantic aliases. Ownership remains local:

| Feature | Theme coverage |
| --- | --- |
| Dashboard shell | Page, header, filters, pickers, management menu, footer |
| Income | Values, privacy control, allocation bar, hidden-value chart state |
| Metrics and cards | Card surfaces, icons, badges, selected and hover states |
| Categories | Rows, headings, donut center, dots, comparison values |
| Trend / purchase activity | Bars, lines, gridlines, legends, refunds, hidden values |
| Events | Panel, cards, category list, summary, transaction table, editor states |
| Recurring | Panel, groups, lifecycle/status pills, composition chart, modal tables |
| Observations | Cards, type markers, evidence tables, review states, insight dialog |
| Transactions | Tables, detail surfaces, event labels, editors, notices |
| Merchants | Browser, editor, alias tables, recurring settings, confirmation states |
| Imports | Steps, tables, warnings, staged decisions, audit surfaces |

Feature-local aliases describe meaning rather than colors. For example:

```css
.recurring-panel-preview {
  --recurring-active: var(--ui-chart-1);
  --recurring-commitment: var(--ui-chart-2);
}
```

The alias remains in `recurring.css`; its palette value remains in shared theme
tokens.

### 5. Visualization palette

Move cross-feature chart-slot references into
`frontend/src/shared/visualization/`. Category, event, observation, and trend
features should not depend on another feature merely to obtain colors.

The shared visualization contract should expose CSS-variable references such
as `var(--ui-chart-1)` through `var(--ui-chart-9)` and
`var(--ui-chart-empty)`. Use the same ordered slots for:

- category donut segments and category dots;
- purchase-activity bars and legends;
- hidden-income and hidden-amount chart states;
- event category indicators;
- observation type markers where a categorical slot is appropriate;
- recurring composition and trend visualizations.

SVG and CSS-rendered charts can consume CSS variables directly. Any future
canvas renderer must resolve the active computed token values before drawing
and redraw after a theme change.

Success, warning, and danger retain their semantic meaning across palettes.
Their exact shades may change to maintain contrast.

### 6. Theme selection workflow

Add a bounded theme feature:

```text
frontend/src/features/theme/
├── ThemePicker.vue
├── theme.ts
└── theme.css
```

The workflow should:

- provide an explicit registry of supported theme identifiers and display
  metadata;
- set `data-clearspend-theme` on the document root;
- save the selected identifier to `localStorage` under a versioned ClearSpend
  key;
- validate stored values and fall back safely to the default;
- tolerate unavailable or failing browser storage;
- restore the preference early enough to avoid a conspicuous wrong-theme
  flash;
- update the root `color-scheme` together with the selected palette;
- expose an accessible menu or listbox with keyboard operation, focus return,
  selected state, and non-color labels;
- sit beside the Manage Data control without changing primary navigation.

Picker styles belong to `features/theme/theme.css`, not the global stylesheet.
`App.vue` owns its placement and integration.

## Implementation phases

### Phase 0 — Branch and baseline

1. Create a dedicated implementation branch from the completed component
   library branch, for example `feature/dashboard-theme-system`.
2. Record the current default-theme desktop, narrow, and modal snapshots.
3. Inventory literal colors in shared UI, global CSS, feature CSS, inline Vue
   styles, and visualization models.
4. Classify every color as foundation, interaction, semantic status,
   visualization, or intentionally fixed brand/provider color.
5. Document any approved exceptions before changing selectors.

Acceptance gate:

- No code from `feature/dashboard-theme-layout` has been merged or
  cherry-picked.
- The inventory identifies the owner and replacement token for every migrated
  color family.
- The current default appearance has a reviewable baseline.

### Phase 1 — Token and palette foundation

1. Complete the semantic token contract in `tokens.css`.
2. Add `palettes.css` with the default palette and reviewed alternatives.
3. Add the shared visualization slot definitions.
4. Import theme files once from the application entry point in an intentional
   cascade order.
5. Add tests that verify every registered palette defines the required token
   contract.
6. Classify every registered palette as light or dark and verify the resulting
   root `color-scheme`.

Acceptance gate:

- Applying any registered root attribute produces a complete token set.
- The default palette remains visually compatible with the approved current
  dashboard.
- No palette file contains feature selectors.
- Browser-provided controls use the correct light or dark scheme before and
  after a live palette change.

### Phase 2 — Shared component migration

1. Replace remaining literal component colors with semantic tokens.
2. Verify every button variant and density in normal, hover, focus, disabled,
   and danger states.
3. Verify inputs and selects in regular/dense, invalid, and disabled states.
4. Verify every dialog tier, including nested overlays and footer treatments.
5. Update the synthetic component gallery or component fixtures for palette
   review without shipping the gallery in production.

Acceptance gate:

- Shared components require no feature-specific theme overrides.
- Light and dark representative palettes pass keyboard review and the numeric
  WCAG contrast gates defined below.
- Opening a teleported modal preserves the selected theme.

### Phase 3 — Dashboard shell and read-only panels

Migrate the application shell, filters, Income & spending, metrics, payment
cards, Categories, Purchase activity, and other read-only panel states.

Treat the following as explicit regression targets:

- category donut segments and empty remainder;
- category dots and legends;
- Purchase activity bars, gridlines, lines, legends, and tooltips;
- Purchase activity and allocation bars while income/amounts are hidden;
- selected periods, cards, hover states, focus rings, popovers, and menus;
- loading, empty, error, and stale/refresh states.

Acceptance gate:

- No sensitive value appears in text, tooltips, charts, or the accessibility
  tree while income is hidden.
- Visualization colors change with the palette and remain identifiable through
  labels or tooltips.
- Desktop and narrow layouts remain unchanged apart from color.

### Phase 4 — Feature workflows and modals

Migrate one complete feature at a time in this order:

1. Events
2. Recurring
3. Observations
4. Transactions
5. Merchants
6. Imports

For each feature:

1. Replace literals with shared tokens or feature-local semantic aliases.
2. Cover panel, modal, tables, controls, notices, statuses, hover/focus, empty,
   loading, error, confirmation, and success states.
3. Keep selectors in the owning feature stylesheet.
4. Run the relevant component and Playwright workflow before moving to the next
   feature.
5. Remove superseded theme overrides immediately; do not accumulate a global
   compatibility layer.

Acceptance gate for each feature:

- The feature owns all of its feature-specific selectors.
- Shared controls obtain color from shared component contracts.
- No workflow or financial behavior changes.
- Representative light and dark screenshots are reviewed.

### Phase 5 — Theme picker and persistence

1. Implement the typed theme registry and validated storage behavior.
2. Add the accessible picker beside Manage Data.
3. Apply the stored preference during startup.
4. Confirm live switching updates open panels, charts, popovers, and dialogs.
5. Confirm reload persistence and safe fallback for removed or invalid themes.
6. Verify versioned preference migration and compatibility aliases for any
   renamed identifier.

Acceptance gate:

- Keyboard users can open, navigate, select, close, and return focus.
- Theme names and selected state are understandable without reading swatches.
- A storage failure does not prevent the dashboard from loading.
- Invalid and retired identifiers resolve to their documented successor or the
  deterministic default.
- Switching themes does not trigger API calls or mutate financial state.

### Phase 6 — Hardening and production build

1. Extend CSS ownership tests to verify the intended theme imports and prevent
   feature selectors from entering palette files.
2. Add a bounded literal-color check for shared components and migrated feature
   families, with documented exceptions rather than a blanket unreliable ban.
3. Validate palette contrast for text, controls, focus indicators, status
   treatments, and chart backgrounds.
4. Verify the dashboard remains understandable in browser forced-colors mode;
   do not disable forced colors globally.
5. Run the complete frontend verification matrix.
6. Build production assets and inspect the generated bundle for private data.
7. Update maintained UI/architecture documentation only if the implemented
   responsibility boundaries differ from this plan.

Acceptance gate:

- All automated checks pass.
- Reviewed snapshots cover the default palette and at least one dark palette at
  desktop and narrow widths, plus representative modal workflows.
- Forced-colors review preserves visible focus, selected state, controls, and
  understandable chart/table output.
- Production assets contain no private data and are generated from source.
- No ignored analysis prototype or financial data is staged.

## Verification matrix

### Accessibility thresholds

Every registered palette must meet these WCAG 2.2 Level AA gates in the states
and color pairings that users actually encounter:

- normal-sized text and text in controls: at least `4.5:1` against its
  background;
- large text: at least `3:1` against its background;
- visual information required to identify controls, selected states, custom
  focus indicators, and meaningful graphical objects: at least `3:1` against
  adjacent colors; and
- category, status, chart, warning, and selection meaning must also be available
  through text, shape, iconography, pattern, position, or accessible labeling.

Disabled controls are exempt from the normative contrast thresholds, but must
remain recognizable as disabled. Contrast automation is a gate, not a
substitute for keyboard, forced-colors, chart-label, and visual review.

### Automated checks

- `npm test`
- `npm run typecheck`
- `npm run build`
- Relevant focused Playwright workflows during each phase
- Complete `npm run test:e2e` before completion
- `.githooks/pre-commit` before any authorized commit

Add focused tests for:

- valid, invalid, missing, and unavailable stored theme preferences;
- versioned stored-preference migration and retired-identifier fallback;
- root theme application and live switching;
- correct root `color-scheme` for every registered palette;
- complete token coverage for every registered palette;
- picker keyboard behavior, accessible labels, selected state, dismissal, and
  focus return;
- modal inheritance while a non-default theme is active;
- chart-slot use in Categories and Purchase activity;
- income-hidden states under both representative light and dark palettes;
- representative forced-colors behavior for controls, focus, selection, and
  data presentation;
- CSS ownership and prohibited global feature overrides.

### Manual review

Review every palette against:

- application shell, filter controls, Manage Data, and theme picker;
- all dashboard panels at desktop and narrow widths;
- every shared button variant and density;
- inputs, selects, table controls, badges, and focus indicators;
- every dialog tier and nested dialog behavior;
- empty, loading, error, warning, success, disabled, selected, hover, and focus
  states;
- Categories, Purchase activity, recurring composition, observation markers,
  and event category colors;
- income hidden and visible states;
- numeric WCAG contrast compliance and non-color state communication;
- browser forced-colors mode, including focus, selection, form controls,
  tables, charts, and dialogs.

## Risks and controls

| Risk | Control |
| --- | --- |
| Monolithic selector overrides return | Palette files define values only; ownership tests reject feature selectors |
| A modal or popover remains static | Apply the contract at the document root and explicitly test teleported/open overlays |
| Charts retain hardcoded colors | Centralize chart slots in `shared/visualization` and test representative chart models |
| Dark palettes expose low contrast | Review semantic states and run contrast checks for every registered palette |
| Native controls render in the wrong scheme | Classify every palette and apply the matching inherited `color-scheme` before first paint |
| Forced colors erase state or chart meaning | Preserve native semantics, visible outlines and labels; verify forced-colors mode explicitly |
| Token or stored theme renames break consumers | Use documented aliases, versioned preference migration and deterministic fallback tests |
| Theme switching changes layout | Keep typography, spacing, radii, and dimensions outside palette overrides |
| Status meaning changes between palettes | Preserve semantic success/warning/danger roles and supplement color with text/icons |
| Income privacy regresses | Test hidden DOM, tooltips, legends, charts, and accessibility output in multiple themes |
| Initial wrong-theme flash | Restore the validated preference before the main UI becomes visible |
| Snapshot suite becomes excessive | Snapshot default plus representative dark coverage; validate all palettes through token and contrast checks |

## Completion criteria

The theme implementation is complete when:

- every registered palette supplies the complete semantic and visualization
  contract;
- the dashboard shell, shared components, panels, modals, menus, tables, and
  charts respond to the active palette;
- no large global feature-selector override block exists;
- feature selectors remain in their owning stylesheets;
- the default theme preserves the approved current appearance and layout;
- representative light and dark themes pass accessibility, privacy, responsive,
  workflow, and visual-regression checks;
- every palette meets the documented WCAG contrast gates and declares the
  correct inherited `color-scheme`;
- forced-colors mode preserves operability, visible focus, state, and access to
  all information;
- the selected theme persists locally and fails safely;
- token and stored-theme compatibility rules are covered by tests;
- frontend tests, type checking, production build, and Playwright workflows
  pass;
- generated production assets contain no private data; and
- implementation changes are reviewed before any commit or push.
