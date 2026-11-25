# Reporting and calculation rules

This document is the source of truth for reporting periods, dates, installments,
income, averages, charts, grouping, and sorting.

## Purchase date and reporting month

The purchase date records when the purchase happened. The reporting month
records when the charge belongs in financial totals. Preserve both.

Determine the reporting month in this order:

1. Provider billing date when supplied.
2. Imported statement month for monthly statement formats.
3. Purchase month only when neither source is available.

Dashboard totals, categories, cards, balance calculations, and month filters use
the reporting month unless a view is explicitly described as purchase activity.

## Trend modes

### One selected month

Show purchases made during that calendar month using purchase dates. The chart
is daily and category-stacked. It explains purchase activity, not the provider's
billing schedule.

Count an installment purchase once in purchase activity rather than showing all
future charges on the purchase day. The summary may separately show billed
charges for comparison.

### Multiple months

Show monthly billed spending. When income is visible and available, compare
monthly income and monthly spending with grouped bars.

Income visibility must follow the same privacy toggle as the income/balance
summary. Hiding income removes it from charts and tooltips as well.

## Installments

Preserve installment number, installment total, billing date/month, and the
source used to derive the reporting month.

These fields participate in duplicate identity. Equal installment amounts in
different months are distinct charges and must not be collapsed as duplicates.

For providers without a billing date, use the imported monthly statement period
when available. Do not fabricate exact billing dates from unsupported evidence.

Changes to installment reconstruction or reporting require before/after totals,
representative plan checks, duplicate checks, and PostgreSQL calculation or
migration tests using synthetic data or an approved disposable PostgreSQL copy.
Run against authoritative data only as an explicitly approved operation after a
verified backup. Add SQLite compatibility coverage only when the maintained
archival/test path is intentionally affected.

## Recurring spending and scheduled obligations

- Only user-reviewed recurring profiles participate in recurring summaries.
- Recurring membership is decided per normalized merchant alias. Several
  included aliases may share one display identity and combined history, while
  excluded aliases under that display identity contribute neither charges nor
  missing-payment expectations.
- Amounts actually billed are spending; expected future windows are
  informational and never increase totals.
- A stopped supplier is `ended`, not `missing`. An end month is sufficient; an
  exact day, end reason, and replacement merchant are not required.
- Ended profiles remain in historical periods but stop appearing as expected or
  missing after their end month.
- Annual obligations appear in a monthly view only when paid, one month before
  the expected month, due, or overdue. They remain available in longer-period
  history.
- Installment commitments remain separate from indefinite recurring profiles.
- Upcoming forecasts cover the current calendar month and next two months in
  the application timezone. Dashboard period and month filters do not move
  that horizon; the card filter still applies.
- Forecasts use reviewed recurring schedules and remaining installments.
  Confirmed persisted charges replace their matching forecast occurrence;
  ambiguous or unsupported evidence is listed as unresolved and is not added
  to expected totals. Pending statement rows are excluded by import staging
  before persistence.
- Expected amounts are explicitly marked as estimates. Month cards display a
  `Known expected` subtotal; unknown amounts remain visible but do not
  contribute to it, and unresolved-source counts appear next to the cards.
  Annual payments and final installments are identified in the payment list.
- An active reviewed monthly fixed profile is expected every month after its
  first confirmed charge; history controls amount confidence rather than
  schedule eligibility. One payment is provisional, two values whose direct
  maximum/minimum ratio is at most 1.15 are developing, and a uniquely
  supported component across at
  least three months is established. Amount proximity is primary; reliable
  dates within three days may distinguish otherwise similar charges. A unique
  stable component may exclude separate ad-hoc charges. Three consecutive
  recent matching months establish a new baseline; competing plausible
  components keep the amount unknown.
- Two-payment similarity is measured directly and order-independently:
  `maximum / minimum <= 1.15`. Comparing each amount with their midpoint is not
  sufficient.
- An established pre-anchor fixed component owns future amount confidence.
  Anchor-month charges are reconciled against it by amount and reliable timing:
  one unique match is confirmed and every unmatched charge remains a separate
  actual. Ambiguous anchor matches do not erase the established future amount.
  Anchor evidence seeds or strengthens an amount only when no established
  pre-anchor component exists.
- Usage-based recurring amounts aggregate positive charges by reporting month
  before taking the recent median and range. Non-monthly schedules keep their
  existing phase and amount-reliability requirements.
- Upcoming exact dates use provider billing dates, or purchase dates only when
  the purchase and reporting months match. A statement month never fabricates
  an exact day. Non-ILS and mixed charged-currency evidence remains an unknown
  amount and is excluded from expected totals.
- A horizon installment actual replaces the same commitment and installment
  number even when it moved to another horizon month; the old projected row is
  removed so the installment is not counted twice, and later installments
  follow the moved occurrence. With no baseline, one valid anchor-month
  installment may seed later horizon projections; a future-only first
  installment cannot create backward or later projections.
- Paused and already-ended recurring profiles do not produce schedule warnings,
  though imported horizon charges remain visible. Malformed horizon installment
  evidence remains visible and is also explained under `Not forecast`.
- A source row with either installment field populated belongs only to the
  installment evidence stream. This includes malformed partial evidence, which
  remains visible once and cannot also become a recurring occurrence.
- `Highest expected` requires complete displayed amounts and no scoped
  unresolved sources; otherwise a unique largest subtotal is `Highest known
  estimate`.

## Financial observations and patterns

This section defines their reporting relationship. Exact eligibility,
thresholds, precedence, grouping, and review behavior are documented in
[`FINANCIAL_OBSERVATIONS.md`](FINANCIAL_OBSERVATIONS.md).

- Month view reports transaction-level observations only. It may surface
  duplicates, recurring or fee changes, category increases, merchant activity,
  large purchases, reliable transaction outliers, and amount-left pressure.
- Latest year and All time do not aggregate monthly observations. They scan for
  lasting changes in spending, amount left, categories, recurring burden,
  installment burden, and merchant habits.
- Latest year reports shifts whose start month is inside the selected year. All
  time reports the strongest lasting shifts across imported history.
- Historical patterns exclude the incomplete current month and isolated large
  purchases. Income-derived patterns require all-card scope, visible income,
  and matching covered income and spending months.
- Routine-spending, category-routine, category-increase, and merchant-habit
  observations exclude transactions assigned to projects or events from both
  the current value and their historical baseline. Transaction-level checks
  such as duplicates, fees, recurring changes, and large purchases still use
  all spending and show the event label as context when one is assigned.
- A spending shift needs three post-change months on the same side of the
  earlier median, with at least two individually crossing both 20% and ₪1,000.
- Category shifts count covered zero-spending months as zero and report the
  merchants that drove the shekel change without claiming that category share
  changed.
- Recurring burden uses normalized monthly equivalents and shows cost and
  active-service count together. Installments remain a separate pattern.
- Merchant habits use purchase dates. Reviewed recurring aliases, installment
  transactions, and money transfers are excluded. A merchant may become regular
  through an average of at least ₪200 per month or through repeated purchase
  frequency: at least six purchases on four purchase days across three
  consecutive active months, or eight purchases on six purchase days in four of
  six months, with little earlier activity.
- Later merchant-frequency growth is folded into the established-habit finding
  rather than emitted as a duplicate observation.
- Review decisions are available only for possible duplicates, additional
  recurring charges, and unusual transactions. They apply to the exact
  transaction group, recurring occurrence, or transaction that was reviewed;
  a different future finding remains eligible.
- Reviewed findings are suppressed from active observation cards but remain
  reversible. Resolving one row in a grouped card does not resolve its other
  rows.

## Income and amount left

- Combine all contributors into one monthly income total.
- Do not expose contributor-level income in the dashboard unless explicitly
  requested.
- Amount left is monthly income minus spending across all cards.
- Percentage left is amount left divided by income when income is non-zero.
- Income and amount-left metrics are all-card household metrics; selecting one
  card must not reinterpret them as card-specific income.
- Missing income is unknown, not automatically zero.

## Reimbursed purchases

- Preserve the original card transaction, card charge, merchant, and category.
- Store a full or partial reimbursement as a separate transaction-specific
  spending adjustment.
- Personal spending is the positive card charge minus the reviewed reimbursed
  amount, never below zero.
- Dashboard spending, categories, cards, averages, amount left, and spending
  trends use personal spending. Original card charges remain available for
  audit and statement reconciliation.
- A reimbursement is not salary, income, or a card refund.
- Removing an adjustment restores the full original charge to personal
  spending without deleting transaction history.
- A future imported bank transfer may be linked as evidence, but must not apply
  the reimbursement a second time.

## Averages

- Average spending uses the applicable recorded months up to the selected point
  or within the selected period.
- Average amount left uses months with usable income and spending information.
- Do not add empty future months to a denominator.
- Expose or test the month counts used by an average so changes cannot silently
  alter its meaning.

## Transactions and grouping

- Individual transaction tables default to purchase date descending.
- Every displayed column must be sortable in both directions when practical.
- Category views default to grouped merchants but allow individual transactions.
- A collapsed merchant row sums matching transactions.
- Expanding it shows the complete individual transaction columns and preserves
  each original statement description.
- Group by canonical display identity plus category. The same display identity
  in different categories must remain in separate groups.
- Transaction-specific category overrides take precedence in reporting without
  rewriting the permanent merchant rule.
- With no query, the all-transactions API returns the newest 1,000 rows in the
  active scope for responsive browsing. A non-empty search runs against the
  complete database history inside the active period, card, and event scope.
- Search is case-insensitive substring matching across original/normalized
  merchant text, canonical display name, and effective category. Selecting
  `All time` therefore searches every imported period, but a selected card still
  limits the result until the user chooses all cards.

## Projects and events

- Event membership is assigned to exact transaction IDs, never to an entire
  merchant or display identity.
- Event spending uses personal amount after any reviewed reimbursement.
- Month-scoped event activity uses purchase date. An event crossing two months
  can appear in both, with only that month's assigned purchases in its amount.
- Event display dates control period visibility; changing them must not add or
  remove transaction membership.
- An event label is independent of category and must not recategorize a
  transaction.
- Category reporting offers `All spending` and `Routine only`. `Routine only`
  excludes exact transactions assigned to an event; it never removes their
  category, changes overall spending, or affects income and amount-left totals.
- A business trip requires an explicit destination. In month views it remains
  an individual event. In Latest year and All time, two or more visible
  business trips with the same normalized destination are grouped for display;
  this computed group must not create another database event or change exact
  transaction assignments.

## Filters

Timeframe, selected month, and card filters must use the same underlying scope
across totals, categories, cards, insights, and transaction details unless a
metric is explicitly defined as all-card, such as household income.

Do not hide a known card from the selector merely because it has no activity in
the currently selected month. Clearly distinguish unavailable activity from an
unavailable card.
