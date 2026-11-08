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
- In the all-transactions table, reimbursement editing uses a compact icon-only
  action column pinned to the right edge. It opens directly without adding an
  expandable transaction row and has an accessible label and tooltip.
- An adjusted transaction continues to show its original charge and clearly
  labels the personal amount and reimbursement status.
- In individual transaction tables, show a compact event label immediately to
  the right of the category. Selecting an existing event saves immediately;
  event creation belongs in event management.
- Do not show one event label on a collapsed merchant row because its underlying
  transactions may belong to different events.
- Event settings allow editing name, type, start/end dates, budget, and status.
  Keep the event details view tabless and open these fields in a separate,
  compact `Edit event` dialog. Do not include a notes field. Date edits affect
  period visibility only and must not change exact transaction membership.
- Create events from the Projects & events panel before assigning individual
  transactions. The creation form includes name, type, dates, optional budget,
  and status; it does not include notes.
- Business trip is a distinct event type. Selecting it reveals a required
  destination field in both create and edit dialogs. Use a blue suitcase icon
  and blue transaction-event label to distinguish it from personal events.
- In a month view, show every business trip as its own event. In Latest year or
  All time, automatically combine two or more visible business trips sharing
  the same normalized destination into one destination group. A single trip
  remains an ordinary event card. The group is a computed view, not another
  stored event.
- Opening a business-trip group shows the same four summary metrics used by an
  individual event, followed by a centered list of its trips. Opening a trip
  from that list shows the normal event details and `Edit event`; use the clean
  back-arrow control to return to the destination group.
- When the selected scope contains no events, collapse Projects & events to its
  header with `No active projects` and the New event action. When no financial
  observation crosses its threshold, collapse that panel to its header with
  `No observations` or `No lasting patterns`. Loading and error states remain
  expanded so their messages are visible.

## Merchant management

- Permanent display-name and alias-category management belongs in the dedicated
  merchant-management experience, not an already crowded transaction modal.
- Show impact before saving: affected aliases, existing transactions, future
  exact matches, and whether categories differ inside one display identity.
- Transaction-specific category correction remains accessible from transaction
  details and must state that it does not change the permanent merchant rule.
- Adding or removing a recurring decision belongs in merchant management. The
  Recurring & commitments modal links there but remains focused on monitoring.
- When a display identity contains several original merchant aliases, recurring
  management must show and save the included aliases explicitly.
- Removing a recurring decision requires confirmation, preserves transactions
  and the previous profile settings, and is distinct from an ended lifecycle.

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
