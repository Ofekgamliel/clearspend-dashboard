# UI component library execution plan

## Status and purpose

Status: proposed execution plan. The theme and visual-token foundation is in
progress; shared Vue components have not started.

This file is the authoritative implementation sequence and checklist for this
initiative. Review files are context only and do not create competing execution
requirements.

This plan turns ClearSpend's existing visual primitives into a small internal
Vue component library. Equivalent controls should share markup, behavior,
accessibility and presentation rather than only global CSS overrides. This
refactor must not change financial results, APIs, persisted data, imports,
observation rules or feature ownership.

Authoritative guidance remains in [`ARCHITECTURE.md`](ARCHITECTURE.md),
[`UI_GUIDELINES.md`](UI_GUIDELINES.md), [`TESTING.md`](TESTING.md) and
[`../AGENTS.md`](../AGENTS.md).

## Executive decision

Build a ClearSpend-owned library inside the existing frontend. Do not adopt a
comprehensive styled framework, globally register components or publish a
separate package. Use local imports and keep the library dependency-light.

Migrate complete, bounded workflow slices, not component types across the whole
application. Each slice introduces only the primitives it needs, fully migrates
one workflow, removes that workflow's superseded CSS and passes verification.
A large feature may require several independently complete workflow slices.

## Ownership and target structure

```text
frontend/src/
  features/                 # financial workflows and feature presentation
  shared/
    ui/                     # generic Vue interaction/presentation primitives
    theme/                  # definitions, tokens and generated palette CSS
    visualization/          # chart-series definitions
    accessibility/          # genuinely accessibility-specific helpers
    format.ts
```

Candidate UI files include `UiButton.vue`, `UiIconButton.vue`, `UiPanel.vue`,
`UiDialog.vue`, `UiField.vue`, `UiInput.vue`, `UiSelect.vue`,
`UiSegmentedControl.vue` and `UiBadge.vue`. Create a file only after the
inventory or implemented consumers demonstrate at least two independent uses,
normally across features. Keep `shared/ui` flat until navigation becomes
difficult, and do not move an existing utility merely to match the target tree.

The theme picker remains a user-facing feature. Theme definitions are shared
infrastructure. Chart colors belong to visualization, not generic UI.

A component qualifies for `shared/ui` only when:

1. The inventory or implemented consumers demonstrate at least two independent
   uses, normally across features. Repetition confined to one domain normally
   remains feature-owned until another independent consumer appears.
2. Its semantic behavior is the same.
3. It contains no financial or feature rule.
4. It makes sense without knowing the consuming feature.
5. Every variant represents a repeated semantic need.

Feature wrappers may compose shared primitives; shared components must never
import feature modules.

Keep focus trapping, restoration and accessible-labelling helpers under
`shared/accessibility`. Keep positioning, stacking, outside-click handling and
scroll locking private to `UiDialog` or the owning component until another
independent overlay demonstrates the same interaction contract. Add a
`shared/interaction` owner only after that reuse is proven.

## Current baseline and prerequisite

ClearSpend already has twelve themes, semantic variables, a stored theme
preference, global visual-consistency selectors, a shared focus directive and
Playwright visual coverage. It does not yet have shared component contracts;
features repeat dialog, button, field and feedback markup and behavior.

Before component implementation, reconcile the in-progress theme and visual
work as a focused change. Verify its tests, screenshots and generated assets,
then commit or deliberately revise it on a focused branch. Do not stack the
component migration onto a documentation archive branch or unrelated dirty
worktree.

Correct these ownership issues during the foundation phases:

- `CATEGORY_COLORS` is owned by Categories while Trend and Events consume it.
- TypeScript theme metadata and CSS palette values can drift.

## Design principles

- Reuse semantic behavior, not appearance alone.
- Preserve native buttons, links, inputs, selects, labels and headings.
- Actions use buttons; navigation uses links.
- Implement and test the interaction required by every ARIA role.
- Prefer finite semantic variants, slots and feature wrappers over arbitrary
  styling or feature-specific props.
- Keep financial content, calculations, validation and workflow state with the
  feature.
- Remove superseded selectors with the verified workflow slice, after their
  known consumers have migrated.

## Theme and token architecture

Maintain semantic tokens for surfaces/text, actions, status pairs, focus,
components, visualization, typography, geometry, spacing, elevation and
motion. Status colors must remain reliable in every theme and must not be
inferred from decorative accents. Chart/category colors are data encodings,
not action or status colors.

Use a typed `ThemeDefinition` catalogue as the authority for identifiers,
metadata, semantic colors and chart colors. Generate palette CSS from it at a
tested build boundary; do not hand-edit generated output. Picker swatches derive
from the same catalogue.

A small pre-paint bootstrap selects the stored generated theme selector before
the Vue application renders. The default theme supplies a readable fallback.
Tests fail when the catalogue, required-token list or generated CSS diverges.
If selection cannot reliably occur before first paint, revise the no-flash
claim instead of equating before-mount with before-paint.

Move chart-series definitions to `shared/visualization/chartPalette.ts`. No
feature may import another feature solely to obtain visual constants.

## Initial component contracts

These are starting boundaries; the pilot must validate them.

### Buttons

`UiButton` renders a native button, defaults to `type="button"`, supports only
demonstrated primary/secondary/danger/ghost treatments, and defines disabled,
busy, `aria-busy`, accessible text and focus-visible behavior. It does not own
navigation, confirmation or saving. A link-like treatment is allowed only for
a genuine repeated action; navigation uses a real link.

`UiIconButton` requires an accessible label and supports only demonstrated
sizes/treatments. The native `title` attribute is not a complete tooltip
solution; any visible tooltip needs its own accessible contract.

### Panel

`UiPanel` owns the frame and demonstrated spacing tiers and exposes title,
subtitle, actions and content. Callers supply heading level or labelling; the
component must not guess hierarchy. Income may retain its documented stronger
summary hierarchy.

### Dialog

Before implementation, record whether to retain a custom teleported dialog or
use native `dialog`. Compare nested dialogs, support, styling, focus behavior
and the existing focus adapter.

The selected contract defines title/description relationships, initial focus,
focus trap/restoration, stacking, missing-trigger behavior, inert background,
scroll locking, Escape/backdrop policy and large/compact tiers. It emits close
requests with reasons such as `escape`, `backdrop`, `close-button` and
`completed`. Features retain open state, dirty/saving policy, validation,
loading and persistence and may reject dismissal.

### Fields

`UiField`, `UiInput` and `UiSelect` preserve native behavior, forward suitable
attributes/events, use stable or caller-supplied IDs, associate labels/help/
errors, support `v-model` without duplicate state, and define required,
readonly, disabled, invalid and autocomplete behavior. Use regular and dense
tiers unless a third repeated semantic need is proven.

### Selection controls

Do not interchange tab, radio-group and pressed-button semantics because they
look segmented. Tabs activate panels, radio groups select one value and pressed
buttons represent toggles. Inventory consumers and use explicit tested modes or
separate primitives; never infer semantics from appearance.

### Badges and feedback

`UiBadge` represents compact status/metadata with demonstrated neutral,
success, warning, danger and info treatments. Feature text and meaning remain
feature-owned, and color is never the only cue. Category/chart treatments do
not belong in this generic badge; use a feature wrapper or separate data-
encoding primitive if repeated.

Inventory feedback before creating components. Distinguish contextual inline
notices, transient global toasts and undo notifications. Create `UiToast`,
`UiInlineNotice` or another primitive only when repeated behavior is proven,
with explicit dismissal, lifetime and live-region politeness.

### Popovers, disclosures and menus

Compare the theme picker, management menu, month picker, card picker and
identity selector. Record semantics, focus, positioning, outside-click, Escape
and keyboard behavior before introducing a shared overlay primitive. A true
ARIA menu/radio-menu must implement its expected keyboard interaction;
otherwise use semantics matching actual behavior.

## Execution phases

### Phase 0 — Reconcile the foundation

- Isolate the current theme/visual work in a coherent review boundary.
- Review theme behavior, guidance changes, screenshots and generated assets.
- Run the complete frontend baseline; commit or deliberately revise the work.

Exit: component work starts from a known, verified state.

### Phase 1 — Inventory and ownership

- Catalogue controls, overlays, feedback, densities and exceptions, including
  native role, keyboard behavior, owner, selectors and known consumers.
- Maintain the catalogue as `docs/UI_COMPONENT_LIBRARY_INVENTORY.md` with these
  columns: existing control; file and feature owner; current consumers;
  native/ARIA semantics; keyboard behavior; density; existing selectors;
  target shared component or feature-owned exception; required tests; and
  migration status.
- Define theme, visualization, accessibility, UI and feature ownership.
- Capture desktop, narrow and modal baselines.
- Fully classify the first bounded pilot; mark uncertain controls as deferred
  feature-owned implementations instead of blocking all work.

Exit: the maintained inventory exists, the pilot is resolved and broader
unknowns are explicitly deferred.

### Phase 2 — Theme, tokens and visualization

- Establish the typed catalogue, generated CSS boundary and safe fallback.
- Record the authoritative source path, generation command/build step, output
  path, tracked-versus-build-only policy, CI stale-output detection, pre-paint
  bootstrap location, storage key and identifier synchronization, and
  no-JavaScript fallback verification.
- Implement or verify pre-paint selection and catalogue-derived swatches.
- Move chart-palette ownership out of Categories.
- Add all-theme completeness, generation, fallback and contrast checks.
- Preserve computed output unless a contrast fix is separately reviewed.

Exit: the generation boundary is documented and enforced without a manual
freshness step; theme values have one authority, cannot silently drift and pass
all-theme checks; visual constants no longer create cross-feature imports.

### Phase 3 — Testing, gallery and CSS ownership

- Add focused Vue component testing when the first interactive primitive needs
  it, documenting the dependency and responsibility. Integrate component tests
  into `npm test` and CI rather than leaving a separate optional command.
- Start a strictly development-only synthetic gallery. It must not appear in
  production navigation, be reachable through a hidden production route or be
  present in the production bundle. Verify exclusion through a test or build
  inspection.
- Define global, component, feature and temporary-compatibility CSS ownership.
- Record every temporary selector and remaining consumer.
- Evaluate an automated accessibility scan such as axe against the gallery or
  Playwright. Adopt it only if results are actionable and low-noise; it never
  replaces deliberate keyboard, focus, dialog, role or screen-reader-semantic
  tests.
- Use cascade layers only if they simplify actual ownership.

Exit: primitives can be reviewed/tested in isolation without private data.

### Phase 4 — First vertical workflow pilot

- Select the smallest bounded create/edit workflow from the inventory; the
  event editor is a candidate, not a predetermined choice.
- Implement only its demonstrated buttons, dialog and form primitives.
- Fully migrate the workflow, remove only its obsolete CSS and add isolated and
  integrated coverage.
- Review desktop, narrow, keyboard, theme and visual results, then commit the
  independently reversible slice.

Exit: the pilot is completely migrated with no financial/API behavior change.

### Phase 5 — Read-only panel pilot

- Compare real panel needs before finalizing `UiPanel`.
- Migrate one panel; verify headings, naming, slots, responsive behavior and
  representative light/dark themes.
- Preserve documented exceptions and remove only that panel's obsolete CSS.

### Phase 6 — Medium-risk workflow slices

Migrate one complete slice at a time, generally in this order unless inventory
shows a safer path:

1. Remaining simple create/edit workflows.
2. Event and category details.
3. Transaction and recurring browsers with nested interactions.
4. Observation details and review feedback.
5. Merchant management.

Each slice introduces only demonstrated primitives, preserves feature wrappers
and state, removes selectors whose consumers migrated, passes all relevant
checks and is committed before proceeding. Badges, feedback, selection and
overlay primitives enter the library only when a slice proves repetition.

### Phase 7 — Staged import

Migrate import last. Preserve dense controls, identity selection,
reconciliation, warnings, insertion preview, keyboard behavior and complete
E2E coverage. Do not alter import validation, semantics or persistence.

### Phase 8 — Cleanup and completion

- Remove remaining obsolete compatibility selectors and unused components,
  tokens, variants, imports and dependencies.
- Review representative visual snapshots and all-theme smoke/contrast results.
- Rebuild generated production assets.
- Update UI guidance and architecture only where behavior/ownership changed.
- Adopt Storybook only if the development gallery demonstrates a limitation.
- Complete the record below.

## Testing strategy

Add an isolated Vue component setup such as Vitest with Vue Test Utils or
Testing Library when the first interactive primitive is introduced. Record the
choice and why Node/Playwright alone are insufficient. Add a dedicated package
script if useful, but make `npm test` and CI run both the existing unit tests and
component tests automatically. Contract tests cover semantic elements,
defaults, variants, density, disabled/busy behavior, events, `v-model`, slots,
ARIA relationships, keyboard/focus, close reasons and token use.

Node tests retain framework-independent presentation logic. Component tests
cover primitives. Playwright covers workflows, nested overlays, keyboard,
responsive behavior, privacy and representative screenshots. Theme tests cover
catalogue/output synchronization, completeness, contrast, persistence, invalid
fallback and all-theme smoke behavior.

Run completeness, contrast and smoke checks across all twelve themes. Check
text/surfaces, actions, focus indicators, semantic statuses, dialogs, popovers,
tables and native controls. Use representative light/dark snapshots rather than
every state multiplied by twelve. Review chart distinguishability with
deterministic checks where useful and human review where ratios are inadequate.

Start the synthetic gallery with the first primitives and add every supported
variant, density, disabled, busy, error, empty and focus state as introduced.

Run after every migration slice:

```bash
cd frontend
npm test
npm run typecheck
npm run build
npm run test:e2e
cd ..
node --test tests/frontend/*.test.js
git diff --check
```

After component tests are introduced, the `npm test` command above includes
them. Review image diffs; updating a snapshot is not proof of correctness. Run
Python synthetic tests only if an API, backend behavior or exchanged contract
changes.

## Acceptance requirements

- Shared components never import features; feature wrappers may compose them.
- Navigation uses links; actions use buttons.
- Dialog close requests identify their reason and support dirty/saving policy.
- Selection controls use explicit tested semantics.
- Every temporary selector has known remaining consumers.
- Tokens and semantic status pairs pass documented contrast in all themes.
- Dark themes cover native controls, dialogs, popovers, tables and feedback.
- Status and charts never rely on color alone.
- Stored invalid themes fall back safely; valid themes select before first paint
  or the documented claim acknowledges a possible default-theme paint.
- Theme changes never alter layout dimensions or financial content.
- The gallery remains synthetic, is unreachable in production and is excluded
  from production output by a verified build boundary.
- Existing behavior is compared before/after every complete workflow slice.
- Motion respects `prefers-reduced-motion`.

## Rollout, rollback and risks

Keep each workflow slice independently reviewable and reversible. Never hand-
edit `dist/`, combine migration with financial changes or delete a selector
before its final consumer migrates. If a slice fails, revert that workflow while
retaining already proven primitives.

| Risk | Mitigation |
| --- | --- |
| Features remain partly migrated | Use complete bounded workflow slices. |
| Similar-looking controls have different meanings | Reuse semantics, not appearance; preserve native roles. |
| Shared props become feature-specific | Require repeated use; prefer slots and wrappers. |
| Old and new CSS compete | Track consumers and remove CSS with verified slices. |
| Stored theme flashes | Test pre-paint selection or revise the claim. |
| Tokens exist but are unreadable | Run all-theme contrast checks. |
| ARIA roles overstate behavior | Test their complete keyboard interaction. |
| Dialog focus/nesting regresses | Decide native/custom explicitly and test focus, stacking and close reasons. |
| All feedback becomes toast | Classify semantics before creating primitives. |
| Theme snapshots become brittle | All-theme smoke/contrast plus representative snapshots. |
| Snapshot churn hides regressions | Review image diffs for every slice. |
| Import regresses | Migrate it last and retain its full E2E gate. |

## Non-goals

- Backend, API, database or financial-rule changes.
- Replacing Vue, Vite, the server or state model.
- A full dashboard redesign or generic chart/table rewrite.
- A separate package, monorepo or publishing pipeline.
- Storybook without demonstrated need.
- Making every current control shared.
- Simultaneously migrating every component type or feature.

## Definition of done

- Theme, visualization, accessibility and UI ownership is documented.
- Cross-feature constants no longer belong to unrelated features.
- Repeated primitives use shared contracts or documented exceptions.
- Feature content, workflows and state remain feature-owned.
- Compatibility selectors are removed or have documented consumers.
- All themes pass completeness, contrast, fallback and smoke coverage.
- Representative visuals and desktop/narrow/keyboard/privacy/write workflows
  are reviewed and pass.
- The gallery contains every implemented state using synthetic data.
- `npm test` and CI include the component contract suite after its introduction.
- UI guidance matches the final contracts; generated assets are rebuilt.
- No private financial data or database change was introduced.

## Completion record

- Final component inventory:
- Remaining exceptions:
- Component-test framework and rationale:
- Test commands and results:
- Theme completeness and contrast results:
- Visual baselines reviewed:
- Generated assets rebuilt:
- Database changes or backups: none expected
- Commit:
- Push or deployment:
