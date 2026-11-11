# Financial observation rules

This document is the source of truth for Financial observations: what each card
means, how it qualifies, how overlapping signals are merged, and which findings
may be reviewed. Observations explain existing data; they never recategorize a
transaction, change a recurring rule, or alter a financial total.

## Shared principles

- Month view finds exceptions and changes within the selected reporting month.
- Latest year and All time find lasting shifts; they never aggregate the cards
  that happened to appear in individual months.
- Current or incomplete months are excluded from historical baselines and
  lasting-pattern detection.
- Comparisons use matching covered periods. Income observations require all-card
  scope, visible income, and months with usable income and spending.
- Routine and habit calculations exclude event-assigned transactions. Exact
  duplicate, recurring, fee, large-purchase, and outlier checks keep them and
  show the event as context.
- Reimbursements use the reviewed personal amount for both the tested purchase
  and the comparison denominator.

## Monthly observations

### Amount left decreased

Shown when amount left is negative, or when both the shekel amount and percentage
of income left materially decline against the previous three complete covered
months. It is hidden whenever income is hidden.

### Category spending increased

Uses routine spending. The category must appear in at least two of the previous
three months. Current spending must be at least twice the three-month median,
at least ₪1,000 above it, and at least 7.5% of current routine spending.

### Possible duplicate

Two or more positive, non-installment rows share original merchant, card,
purchase date, charged amount, and currency. The application does not delete or
merge either charge until the user reviews the exact group.

### Additional recurring charge

A reviewed recurring pattern has more than one non-identical charge inside one
expected billing occurrence. Monthly learned cycles require at least three
earlier day observations and use a seven-day window around the expected date.
An exact same-charge pair is handled as a possible duplicate instead.

### Recurring amount increased

A specific reviewed fixed recurring payment rises by at least ₪1 against its
established baseline. Foreign-currency subscriptions are compared in their
original currency; a shekel exchange-rate change alone does not qualify. A
reviewed variable bill qualifies only when it exceeds its observed range.

### Fee amount increased

A reviewed fixed fee rises by at least ₪1, or a variable fee exceeds its recent
observed range. A merchant name containing a fee-like word is evidence of a fee,
not proof that its amount should be fixed.

### First fee observed

No earlier matching fee appears in the previous 12 imported months. The card is
worded as `first observed`, not `confirmed new`, because imported history may not
prove that no earlier fee existed outside available coverage.

### Merchant activity changed

For a routine, non-event merchant, the previous three active months must include
at least two active months and five earlier purchases. Current monthly spending
must be at least 1.75 times and ₪200 above the median, or current count must be at
least twice and three purchases above the baseline.

### Large purchase

The reviewed personal amount is at least ₪500 **and** at least 7.5% of positive
personal spending in the same month and card scope. Insufficient history does
not prevent a factually large purchase from being shown.

### Unusual transaction

Uses the previous six months, excluding the tested transaction. Eligibility
requires at least five purchases across three months, with at least 75% of
amounts within ±30% of their median. The new amount must be at least 2.5 times
the median and at least ₪100 above it. Passing the stability test alone produces
no card.

If one purchase is both large and unusual, show one `Large and unusual purchase`
finding. A merchant-level activity finding suppresses a redundant individual
outlier explanation for the same behavior. Normal matched recurring charges are
not emitted as generic large or unusual findings.

## Latest-year and all-time patterns

Latest year shows meaningful shifts that began inside the selected year, when
they began, and whether they remain visible. All time shows the strongest lasting
shifts across imported history. Both exclude the incomplete current month.

### Spending routine shifted

Compare three post-change months with the median of up to six earlier months
(at least three required), excluding event spending. All three post months must
be on the same side, and at least two must individually cross both 20% and
₪1,000. One isolated spike cannot establish a new routine.

### Amount left trend

Use the same fully covered months for income and spending. Severity order is:

1. Spending exceeded income in at least two of three recent months.
2. Spending grew by at least 10% and at least ten percentage points faster than
   income.
3. Amount-left shekels and percentage moved in the same direction by at least
   ₪1,500 and ten percentage points.

If shekels and percentage disagree, show both facts in details rather than a
single directional claim. Skip percentage comparisons when the relevant income
or growth baseline is zero.

### Category routine shifted

Compare three post-change months with an established pre-period, excluding event
spending. Covered months with no category spending count as zero. At least two
post months must individually cross the threshold and all three must be on the
same side. An increase is at least 1.5 times and ₪500 above baseline; a decrease
is at most 60% of and ₪500 below baseline. Show the driving merchants and each
finding's own period; do not claim category share changed without a separate
share calculation.

### Recurring burden shifted

Shows a lasting change in monthly commitment cost, active service count, or both.
Annual scheduled charges contribute their monthly equivalent. Details identify
which reviewed services started, ended, or changed amount.

### Persistent installment burden

Shows a material installment burden sustained for six months. `Payments stayed
high` and `new plans replaced ending plans` are separate explanations: one long
plan can cause persistence, while replacement requires plan-level start/end
evidence.

### Merchant habit shifted

Excludes event transactions, reviewed recurring aliases, installments, and money
transfers. A merchant can become regular through average spending of at least
₪200 per month, or through frequency with little earlier activity:

- at least six purchases on four purchase days across three consecutive active
  months; or
- at least eight purchases on six purchase days in four of six months.

Later frequency or typical-amount changes are folded into the established habit
instead of creating a second redundant card. `Typical purchase amount increased`
describes the observed amount; it does not claim a price increase.

## Grouping and evidence

Cards of the same type may group several findings. The card shows the number of
findings and a concise merchant or category summary. The modal keeps one
centered, scrollable row per finding with its observed value, baseline, result,
and exact period. One merchant may have several findings and several merchants
may contribute to one grouped card; those counts are not interchangeable.

Evidence starts collapsed. Opening a related transaction or recurring
occurrence navigates to the corresponding application detail rather than acting
as a decorative button.

## Reviewable findings

Only judgment-based findings have a resolution:

- `Possible duplicate` → `Not duplicate`
- `Additional recurring charge` → `Expected charge`
- `Unusual transaction` → `Not unusual`

Other cards are factual explanations and remain visible. A review suppresses
only the exact transaction group, recurring occurrence, or transaction identified
by its structured finding key. It does not silence the merchant permanently and
does not suppress a different future finding. Reviews are stored locally in
`observation_reviews`, removed from active cards, and remain reversible through
the temporary undo action.
