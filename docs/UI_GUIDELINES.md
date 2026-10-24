# UI guidelines

This document is the source of truth for stable ClearSpend interaction patterns
and the review process for substantial interface changes.

## Design process

For a significant layout, navigation, chart, or editing-flow change:

1. Explain the proposed behavior and tradeoffs.
2. Create a separate review prototype when requested.
3. Use synthetic data in any tracked prototype.
4. Obtain approval before replacing the production interaction.
5. Back up relevant files and the database when the implementation can mutate
   persisted state.
6. Verify the production flow with real local data without copying that data
   into tracked assets.

Local review prototypes derived from real dashboard data must remain ignored.

## Data presentation

- Production UI values come from the local API; do not hardcode live values.
- Preserve both purchase date and reporting/billing information in detailed
  transaction views.
- Use the existing category-color system consistently in donut charts, stacked
  daily bars, legends, and tooltips.
- Tooltips must identify the represented category or metric rather than relying
  on color alone.
- Empty states and missing values must be explicit; do not display fabricated
  zeros or demo transactions.

## Transactions

- Default individual transactions to purchase date descending.
- Column headers act as sort controls and expose the active sort direction.
- Category transaction views offer grouped and individual modes.
- Collapsed rows summarize one display identity and category.
- Expanded rows show all available transaction fields, not a reduced four-field
  subset.
- Preserve original merchant descriptions inside expanded/individual details.
- Use a compact edit affordance, such as the approved edit icon on hover/focus,
  instead of repeating a large action beneath every category.

## Merchant management

- Permanent display-name and alias-category management belongs in the dedicated
  merchant-management experience, not an already crowded transaction modal.
- Show impact before saving: affected aliases, existing transactions, future
  exact matches, and whether categories differ inside one display identity.
- Transaction-specific category correction remains accessible from transaction
  details and must state that it does not change the permanent merchant rule.

## Income privacy

- Income and balance information can be hidden.
- The same control governs income cards, chart bars, legends, and tooltips.
- Do not reveal hidden income through secondary labels, accessibility text, or
  stale chart elements.
- Income comparisons are shown only where the reporting scope supports the
  all-card household calculation.

## Filters and navigation

- Keep timeframe controls visually separate from month and card selectors.
- Preserve one shared filter state across dashboard panels and detail views.
- Category and card panels must reflect the selected timeframe accurately.
- Management/import actions should be discoverable without competing with the
  primary analytical content.

## Accessibility and responsive behavior

- Every icon-only action requires an accessible label.
- Hover-only actions must also appear on keyboard focus and remain operable by
  keyboard.
- Sort controls must expose `aria-sort` or equivalent state.
- Do not rely on color alone to communicate category, warning, or selection.
- Tables may scroll horizontally rather than silently removing important data.
- Verify major interactions at desktop and narrow viewport widths.
