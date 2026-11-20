# Dashboard themes

This document is the source of truth for ClearSpend's selectable dashboard
color schemes. Themes change presentation only; they do not change layout,
financial calculations, API requests, reporting scope, or persisted financial
data.

## Available themes

The default is **Current violet**. The registry currently contains eight
stable identifiers:

| Identifier | Display name | Scheme |
| --- | --- | --- |
| `current` | Current violet | Light |
| `clay` | Clay & sky | Light |
| `plum` | Plum & apricot | Light |
| `rose` | Rose & gold | Light |
| `graphite` | Graphite & amber | Dark |
| `navy` | Navy & coral | Dark |
| `steel` | Steel & electric | Dark |
| `ruby` | Ruby night | Dark |

Previously explored identifiers including `sand`, `sage`, `forest`, `ocean`,
`cobalt`, and `midnight` are not supported. Stored unsupported identifiers fall
back to `current`.

## User behavior and persistence

The palette button beside **Manage data** opens the theme picker. A selection
is applied to `document.documentElement` through
`data-clearspend-theme="<identifier>"` and updates the native `color-scheme`.
The browser-local preference uses the versioned `clearspend-color-theme`
storage key. It does not require a backend setting or database migration.

The pre-render bootstrap validates and applies the stored identifier before the
Vue application renders. Missing, malformed, retired, or unsupported values
fall back safely to `current`.

## Ownership

| Responsibility | Source |
| --- | --- |
| Stable identifiers, display metadata, scheme and storage behavior | `frontend/src/features/theme/theme.ts` |
| Picker interaction and presentation | `frontend/src/features/theme/ThemePicker.vue` and `theme.css` |
| Default foundation and semantic aliases | `frontend/src/shared/theme/tokens.css` |
| Non-default palette values | `frontend/src/shared/theme/palettes.css` |
| Cross-feature chart slots | `frontend/src/shared/visualization/chartPalette.ts` |
| Feature-specific use of semantic tokens | The owning file under `frontend/src/features/` |
| Production assets | Generated `dist/`; never edit by hand |

The application and shared components consume stable `--ui-*` semantic tokens.
Palette files define only the `--theme-*` foundation values and must not contain
feature selectors. Category charts, Purchase activity, income-hidden charts,
legends, dialogs, menus, tables, inputs, buttons, overlays, focus states, and
status treatments all derive from the same semantic contract.

Typography, spacing, radii, component density, and dialog dimensions are not
palette properties. Their ownership remains with the shared component or
feature layout that defines them.

## Adding or changing a theme

1. Add or update its typed metadata in `features/theme/theme.ts`.
2. Define the complete `--theme-*` contract in `shared/theme/palettes.css`.
3. Keep an existing identifier stable when only its label or values change.
4. Update the pre-render allowlist in `frontend/index.html`.
5. Update this document's theme table.
6. Verify components, feature-owned content, dialogs and charts at desktop and
   narrow widths.
7. Rebuild `dist/`; do not edit generated assets directly.

Removing a theme requires an explicit fallback or migration decision for its
stored identifier. A removed identifier must never leave a partially inherited
palette.

## Accessibility and verification

Every palette must retain readable text, visible focus, distinguishable control
states, and semantic success, warning and danger meaning. Charts and statuses
must provide labels or other non-color information. Forced-colors mode must
remain operable.

Run the frontend unit and component tests, type checking, the production build,
and relevant Playwright workflows. Theme tests verify unique identifiers,
storage fallback, root application, native scheme selection, complete palette
contracts, and pre-render registration. Review representative light and dark
themes visually, including teleported dialogs and income-hidden states.

The completed implementation requirements and original acceptance criteria are
preserved in
[`archive/DASHBOARD_THEME_IMPLEMENTATION_PLAN.md`](archive/DASHBOARD_THEME_IMPLEMENTATION_PLAN.md).
