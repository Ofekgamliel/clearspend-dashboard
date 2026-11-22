# Dashboard skeleton loading plan

## Status and purpose

This plan defines how ClearSpend should introduce dashboard skeleton loading
after moving its authoritative financial state to remote Supabase PostgreSQL.
Remote reads add visible latency when the user changes the reporting period,
month, or card. Skeletons should make that wait feel stable and intentional
without concealing performance problems or showing financial values from the
wrong scope.

This is a presentation and interaction change. It must not alter reporting
rules, request parameters, API contracts, financial calculations, or database
behavior.

The plan incorporates the completed design review in
`docs/DASHBOARD_SKELETON_LOADING_PLAN_REVIEW.txt`. Core implementation is now
present on `feature/dashboard-skeleton-loading`: runtime and dashboard loading
are separated, responses are scope-bound, dashboard and independent panels use
feature-owned skeleton layouts, and deterministic loading workflows are tested.
Real remote-endpoint measurement and the optional request-cancellation follow-up
remain separate work; cancellation is not required for correctness.

## Goals

- Preserve the dashboard layout while data is loading.
- Prevent values from the previous period or card from appearing under a newly
  selected filter.
- Distinguish initial loading, filter-driven scope changes, background refresh,
  empty results, and failures.
- Let independently loaded panels finish progressively.
- Keep skeletons out of the accessibility tree while announcing useful loading
  status once.
- Respect income privacy, reduced-motion preferences, responsive layouts, and
  every supported theme.
- Keep loading-state ownership consistent with the existing Vue architecture.

## Non-goals

- Treating skeletons as a substitute for measuring or improving remote query
  performance.
- Changing backend response structures or moving financial calculations into
  Vue.
- Creating fake example transactions, merchants, values, dates, or chart data.
- Replacing documented empty, error, retry, or disconnected-runtime states.
- Adding skeletons to every dialog and management workflow in the same change.
- Introducing a global loading store.

## Core interaction model

ClearSpend should distinguish three loading modes.

### Initial dashboard load

After the runtime health check succeeds, render the dashboard frames and their
skeleton content until real responses arrive. Keep the application header and
filters visible. Panels with independent endpoints may replace their skeletons
as soon as their own requests succeed.

The runtime connection check remains its own existing state. A dashboard
skeleton must not imply that the application is connected before runtime and
database health have been verified.

Runtime health and dashboard loading must be sequenced independently:

1. Perform the runtime and database health request while showing the connection
   state.
2. If health fails, keep the dashboard unmounted and show the existing
   connection error and retry action.
3. If health succeeds, mark the runtime ready and end the connection-checking
   state immediately.
4. Start the dashboard request as an initial dashboard load without awaiting it
   inside the runtime-checking state.
5. Mount Categories, Events, Recurring, and Observations at the same time so
   their independent requests can run concurrently with the dashboard request.

`verifyRuntime()` must therefore not keep `runtimeChecking` active until the
first `/api/dashboard` response finishes. A dashboard failure after successful
health verification is a dashboard error, not a runtime connection failure.

### Reporting-scope change

When the period, month, or card changes:

1. Update the selected filter immediately.
2. Mark the affected dashboard and feature-panel requests as loading.
3. Remove old financial values and interactive data controls from presentation.
4. Preserve panel frames, headings, and approximate final dimensions.
5. Show scope-appropriate skeleton structures until each new response arrives.
6. Accept only the newest request result.

The previous response must not remain visible beneath an `Updating…` label.
Once a filter displays a new scope, showing old values can misrepresent which
period or card those values belong to.

Scope changes include feature-local controls that change the meaning of a
response, not only shared dashboard filters. In particular:

- switching Categories between All spending and Routine only is a category
  scope change;
- changing `incomeHidden` is an observation scope change and must remove old
  income-related observation content immediately; and
- each independent feature must identify any other local response-shaping
  control and include it in that feature's scope identity.

### Same-scope refresh

After a mutation such as a reimbursement edit, merchant change, event update,
observation review, recurring change, or approved import, preserve current
same-scope content where it remains safe and show a restrained updating state.

Do not replace the complete dashboard with skeletons for every small mutation.
Prefer refreshing only affected panels when ownership is known. A full refresh
may retain the current same-scope response while setting `aria-busy` and showing
one subtle progress indicator.

If a mutation changes the active scope or invalidates the meaning of displayed
values, use the scope-change behavior instead.

## Loading-state ownership

`frontend/src/features/dashboard/useDashboardData.ts` remains the owner of
shared dashboard filter loading. Extend its state from one ambiguous `loading`
boolean to a small explicit model, for example:

```ts
type DashboardLoadMode = 'idle' | 'initial' | 'scope-change' | 'refresh';
```

Load mode alone does not establish whether a response is safe to display. The
composable must also associate each request and successful response with a
stable scope identity. The exact representation may differ, but it should be
equivalent to:

```ts
interface DashboardRequestState {
  mode: DashboardLoadMode;
  selectedScopeKey: string;
  responseScopeKey: string | null;
  activeRequestId: number;
  error: string;
}
```

The dashboard scope key must be derived from the parameters actually sent to
the endpoint: period, requested month, and card. It must not depend on
`effectiveMonth`, because that value is partly derived from an earlier
response. Each independent feature should define its own key from all shared
and local parameters that shape its response.

The exact representation may differ, but callers must be able to distinguish:

- whether a request is active;
- whether `responseScopeKey` matches `selectedScopeKey`;
- whether safe same-scope content may remain visible; and
- whether the current state is initial, refreshing, empty, or failed.

Render financial values only when the successful response identity matches the
currently selected scope. Initial loads and scope changes have no displayable
response and use skeletons. A same-scope refresh may retain its matching
response. A response for an older identity must be ignored even if it finishes
successfully.

The dashboard composable continues to own request ordering. Request-ID
protection remains the correctness mechanism so an older response cannot
replace a newer selection. `AbortController` is optional: browser cancellation
does not guarantee that a Python handler or PostgreSQL query stops after the
request reaches the server. Add cancellation only after the state behavior is
complete and measurement shows a practical benefit.

Categories, observations, recurring, events, and other independently loaded
features retain their own request state. They should adopt the same state
semantics rather than moving all panel requests into the dashboard composable.

## Dashboard panel rendering contract

After runtime health succeeds, `App.vue` must mount dashboard-owned panels even
when no `DashboardResponse` exists yet. Income, Metrics, Trend, Cards, and
Recent transactions currently depend on `v-if="dashboard"`; implementation
must replace that all-or-nothing mount behavior with an explicit loading
contract.

- Pass nullable feature data together with the explicit loading mode.
- During initial loading and scope changes, pass no displayable financial data.
- During a same-scope refresh, retain only data whose response identity still
  matches the selected scope.
- Let each feature own its skeleton, real-content, empty, and error branches.
- Do not construct a fake `DashboardResponse` with zeroes or sample financial
  values to satisfy required component props.

Keep known month and card navigation options stable while a new response is
pending where those options remain valid navigation metadata. Clear stale
financial content without collapsing the filter layout. Disable data-dependent
actions, including View all transactions, until selected scope and response
scope agree.

## Component ownership

### Shared skeleton primitive

Add a shared primitive only after recording its demonstrated consumers in
`docs/UI_COMPONENT_LIBRARY_INVENTORY.md`. Skeleton shapes will be used by more
than two independent dashboard features, so a small `UiSkeleton` primitive is
appropriate.

`UiSkeleton` should own only generic presentation and accessibility behavior:

- line, block, and circle shapes;
- shared base and highlight colors;
- animation and reduced-motion behavior;
- decorative `aria-hidden="true"` behavior; and
- finite semantic shape variants rather than feature-specific styling.

It must not know about transactions, categories, cards, income, charts, or
reporting periods. It must not import feature modules.

### Feature-owned skeleton layouts

Each feature owns the arrangement that mirrors its actual content. A feature
may place `UiSkeleton` directly in its component or use a small feature-local
skeleton component when that keeps the production template readable.

Feature skeleton layouts must preserve the real panel's spacing and responsive
behavior. They may not invent reusable financial semantics inside
`frontend/src/shared/`.

## Panel designs

### Income and spending

- Keep the panel heading and privacy control visible.
- Replace the three primary values with line placeholders.
- Show a neutral allocation-bar placeholder.
- Show the monthly-average heading and two representative rows.
- Never expose previous income values in visible text, hidden DOM content,
  tooltips, labels, or accessibility text.
- If income is hidden, keep privacy semantics intact and render only generic
  decorative placeholders.

### Key metrics

- Preserve the four-card grid and its narrow-layout behavior.
- Each card should contain a label line, a large value line, and a supporting
  line or neutral mini-visual placeholder.
- Do not render currency symbols, counts, or fake chart heights as data.

### Trend

- Keep the panel title visible.
- Replace the subtitle and legend values with restrained line placeholders when
  they depend on the response.
- Preserve the chart height with neutral axes/grid structure and several
  non-semantic bar or line blocks.
- Skeleton chart elements are decorative and must not expose chart roles,
  focus targets, tooltips, or fabricated accessible labels.

### Categories

- Keep the heading visible.
- Keep the scope control available, but treat All spending versus Routine only
  as part of the category response identity and remove old-scope values
  immediately. Disable detail actions whose meaning depends on unavailable
  data.
- Use a neutral circular or donut-shaped placeholder and approximately five
  representative category rows.
- Do not use real category colors, names, percentages, or comparison badges.
- Preserve the documented explicit empty and error states after loading ends.

### Spending by card

- Keep the heading visible.
- Show two or three representative card rows with logo, label, amount, and bar
  placeholders.
- Do not render card suffixes, provider identities, or fake totals.
- Disable row selection until the response belongs to the active scope.

### Financial observations

- Keep the panel expanded while loading, as required by the current UI
  guidelines.
- Preserve the heading and use representative observation-card blocks.
- Do not show previous finding counts, titles, evidence, or review actions.
- Include `incomeHidden` in the observation scope identity. If income is hidden
  during an active request, immediately remove the old response from visible
  content, hidden DOM, tooltips, dialogs, and the accessibility tree.
- Only collapse to `No observations` or `No lasting patterns` after the request
  successfully returns an empty result.

### Recurring and commitments

- Preserve the panel frame and heading.
- Use representative summary, composition, and series-row placeholders.
- Do not show previous verdict counts, expected charges, lifecycle states, or
  edit actions under a new reporting scope.

### Projects and events

- Keep the panel expanded while loading.
- Preserve the heading and New event action only if that action is independent
  of the pending response.
- Use representative event-card placeholders without names, dates, budgets, or
  totals.
- Only collapse to `No active projects` after a successful empty response.

### Recent transactions

- Keep the panel heading and table frame.
- Preserve the table header and show approximately five skeleton rows.
- Do not leave old merchants, categories, card suffixes, dates, or amounts in
  the DOM after a scope change.
- Disable `View all transactions` until the displayed scope and response agree,
  unless the transaction browser independently guarantees the new scope.

## Accessibility contract

- Apply `aria-busy="true"` to every loading panel or meaningful loading region.
- Give skeleton elements `aria-hidden="true"` and no accessible names.
- Do not give decorative chart or table skeletons roles such as `img`, `table`,
  `row`, or `button` unless real usable semantics are present.
- Provide one polite status announcement for a dashboard scope change, such as
  `Updating dashboard for Latest year`.
- Own that announcement in `App.vue` or the dashboard composable; individual
  panels should use `aria-busy` without competing live regions.
- Avoid simultaneous `role="status"` announcements from every panel.
- Preserve `role="alert"` for actionable failures and keep retry controls
  keyboard accessible.
- Remove or disable interactive controls associated with unavailable content.
- Do not move keyboard focus merely because loading begins or ends.
- If a focused control becomes unavailable, preserve focus on a stable parent
  action or handle the transition explicitly.
- Honor `prefers-reduced-motion: reduce` by removing shimmer movement and using
  a static neutral placeholder.

## Visual and theme contract

Introduce semantic theme values such as:

```css
--ui-skeleton-base
--ui-skeleton-highlight
```

The exact names may follow the existing token conventions. Skeleton colors
must be defined in the shared theme tokens and derive from existing surface and
border semantics rather than hard-coded gray values or unnecessary per-theme
overrides.

Use one restrained animation across the application. Avoid staggered waves,
fast pulsing, or independent animations that make the full dashboard visually
noisy. Skeleton animation must not obscure panel borders, headings, focus
indicators, errors, or privacy controls.

Representative light and dark themes require human visual review. Token
completeness checks should cover all supported themes.

## Layout stability

- Match the approximate height of each populated panel at desktop and narrow
  widths.
- Preserve dashboard grid columns and gaps.
- Avoid a single fixed height when a feature already has meaningfully different
  month, year, empty, or narrow layouts.
- Use a bounded number of representative rows rather than matching the eventual
  result count.
- Keep panel headers stable so users can understand what is loading.
- Avoid whole-page disappearance or large vertical jumps as panels resolve.

## Error and empty-state behavior

Skeletons represent only an active request. They must disappear when the
request succeeds or fails.

The state order should be explicit:

```text
loading -> skeleton
success with data -> real content
success without data -> documented empty state
failure without usable content -> error and retry
same-scope refresh failure with usable content -> retained content plus error
```

Never convert an error into an empty state. Never leave a skeleton visible
after a request has failed.

Failures have two distinct presentation paths:

- An initial-load or scope-change failure has no usable matching response. End
  the skeleton state and show the panel's blocking error with a retry action.
- A same-scope refresh failure retains the valid matching response and shows a
  restrained refresh error with an appropriate retry action. It must not turn
  valid content into an empty state or full blocking error.

## Performance considerations

Skeletons improve perceived responsiveness but do not reduce database or
network latency. Measure the affected endpoints before and after this work.

Record at least:

- dashboard request duration by period;
- categories, observations, recurring, events, and transaction request
  duration;
- time from filter interaction to first updated panel;
- time until all visible panels settle; and
- the number of obsolete requests created by rapid filter changes.

Continue backend query and round-trip optimization where measurements justify
it. If very short requests produce distracting flashes, prefer a small
appearance delay and CSS transition.

If skeleton appearance is delayed to prevent flashes, stale scope data must
still disappear immediately. Do not introduce a minimum display duration that
slows fast responses.

## Implementation phases

### Phase 1: runtime sequencing and loading contract

1. End runtime checking immediately after successful health verification and
   start dashboard and independent-panel requests concurrently.
2. Define dashboard load modes, selected and response scope identities,
   request ordering, and blocking versus refresh errors.
3. Make dashboard-owned panels mountable with nullable response data.

### Phase 2: shared primitive

1. Add the demonstrated skeleton consumers and ownership rules to the UI
   component inventory.
2. Add the generic shared skeleton primitive and semantic theme tokens.
3. Add component tests for variants, decorative semantics, theme behavior, and
   reduced motion.
4. Add a synthetic shared-component gallery example.

### Phase 3: dashboard-owned response panels

Apply scope-change skeletons to:

- Income and spending;
- Key metrics;
- Trend;
- Spending by card; and
- Recent transactions.

These panels share the main dashboard response and should establish the final
loading-state interaction before independent endpoints are migrated.

### Phase 4: independently loaded panels

Apply the same state model to:

- Categories;
- Financial observations;
- Recurring and commitments; and
- Projects and events.

Preserve each feature's existing request ordering, retry behavior, empty-state
rules, and mutation ownership. Add Categories' local spending scope and
Observations' income-visibility state to their response identities.

### Phase 5: deterministic browser coverage and refinement

1. Add deterministic delayed, reordered, and failed-response browser workflows.
2. Confirm rapid switching always settles on the newest scope.
3. Measure real endpoint latency separately from loading-state tests.
4. Measure whether any remaining loaders belong in dialogs or management
   workflows as a separate future change.
5. Remove obsolete `Loading…` and `Updating…` labels only where the new shared
   status contract replaces them.

### Optional follow-up: request cancellation

Add `AbortController` only for compatible obsolete GET requests and only if
measurement shows useful client-side savings. The work is complete without
cancellation when request IDs and response-scope identities guarantee correct
display behavior.

## Test plan

### Component and composable tests

- Initial load renders skeletons and no financial values.
- Dashboard and independent feature requests begin after health succeeds
  without waiting for `/api/dashboard` to finish.
- A period change removes previous-period values immediately.
- A month change removes previous-month values immediately.
- A card change removes previous-card values immediately.
- A category-scope change removes the previous category response immediately.
- Changing income visibility during an observation request cannot expose the
  previous income-related response.
- A same-scope refresh retains safe content with the restrained refresh state.
- The newest request wins after rapid filter changes.
- A stale response for an old period, month, card, category scope, or income
  visibility state cannot replace or appear under the selected scope.
- Success replaces skeletons with real content.
- Empty success renders the documented empty state.
- An initial or scope-change failure removes skeletons and renders a blocking
  retryable error.
- A same-scope refresh failure retains matching content and renders a
  restrained refresh error and retry action.
- Skeletons are decorative and loading regions expose `aria-busy`.
- Reduced-motion mode disables shimmer movement.
- Hidden income never appears during loading or refresh transitions.

### Browser workflows

- Verify initial dashboard loading at desktop and narrow widths.
- Verify month, latest-year, all-time, and card transitions.
- Verify rapid consecutive filter changes.
- Use Playwright request interception with synthetic data to verify delayed,
  reordered, failed, and, if implemented, aborted responses deterministically.
- Verify initial loading contains no financial values in visible text or the
  accessibility tree.
- Verify a same-scope refresh retains valid content instead of replacing the
  dashboard with skeletons.
- Verify keyboard focus remains stable during loading.
- Verify period controls remain understandable and operable.
- Verify representative light and dark theme snapshots.
- Verify no layout shift obscures the header, filters, or retry controls.

### Required commands

Run the applicable existing verification from the repository root:

```bash
PYTHONPATH=src:. .venv/bin/python -m unittest discover -s tests/synthetic -v
node --test tests/frontend/*.test.js
cd frontend
npm test
npm run typecheck
npm run build
npm run test:e2e
```

Review generated `dist/` changes and confirm that no financial data or private
runtime metadata is embedded in production assets.

## Documentation updates

When implementing this plan:

- update `docs/UI_GUIDELINES.md` with the initial, scope-change, and refresh
  loading contract;
- update `docs/UI_COMPONENT_LIBRARY_INVENTORY.md` before adding `UiSkeleton`;
- update `docs/ARCHITECTURE.md` only if loading-state ownership or shared module
  boundaries change materially;
- update `docs/TESTING.md` if a new reusable slow-response or loading-state
  browser workflow becomes part of required acceptance; and
- keep API and financial-domain documentation unchanged unless their contracts
  genuinely change.

## Acceptance criteria

The skeleton-loading work is complete when:

- the dashboard never presents old-scope values under a new selected filter;
- successful runtime health mounts the skeleton dashboard and starts dashboard
  and independent feature requests concurrently;
- every response is displayed only when its scope identity matches the selected
  scope;
- initial and scope-change loads use stable structural placeholders;
- same-scope refreshes avoid unnecessary whole-dashboard replacement;
- blocking failures and same-scope refresh failures retain their distinct
  presentation and retry behavior;
- independently loaded panels resolve progressively;
- skeleton elements expose no fabricated financial information or accessible
  content;
- one useful loading announcement replaces repeated panel announcements;
- errors and explicit empty states remain intact;
- income privacy remains a data-exposure boundary;
- reduced-motion behavior is static and usable;
- desktop and narrow layouts remain stable;
- supported theme tokens and representative visual snapshots are verified;
- component, type, build, and browser checks pass; and
- measured endpoint latency is recorded separately from perceived-loading
  improvements.
