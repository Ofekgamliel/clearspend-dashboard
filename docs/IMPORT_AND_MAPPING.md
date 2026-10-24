# Import and merchant-mapping rules

This document is the source of truth for statement imports, duplicate handling,
merchant classification, display identities, and transaction overrides.

## Staged import lifecycle

New statement files must follow this sequence:

1. Recognize the provider and file format.
2. Parse and normalize rows without modifying the live transaction set.
3. Identify the card and statement period when available.
4. Compare file, statement, and transaction identities with the database.
5. Reuse approved merchant decisions before suggesting new ones.
6. Present duplicates, installments, unresolved merchants, and reconciliation
   status for review.
7. Require explicit approval for unresolved or permanent decisions.
8. Back up the database.
9. Commit the approved batch and record the import audit result.

Analyzing or staging a file must not insert transactions or permanent mappings.

## Duplicate protection

Duplicate checks operate at three levels:

1. Exact file fingerprint detects a byte-for-byte re-upload.
2. Semantic statement fingerprint detects different files containing the same
   normalized transaction set.
3. Transaction identity detects overlap across statements and formats.

Transaction identity includes provider, card, relevant dates, normalized
merchant, charged and original amounts/currencies, installment metadata, and an
occurrence counter. The occurrence counter preserves legitimate repeated rows.

Do not simplify identity in a way that removes equal installment charges from
different reporting months or merges genuine same-day repeated purchases.

## Reconciliation

When a provider exposes an official statement total, compare it with the parsed
total. If the source format does not expose a reliable total, show that manual
reconciliation is required rather than claiming the file reconciled.

A mismatch is a warning requiring review. Do not silently discard rows to make
the numbers match.

## Merchant classification priority

Use the following order for every imported merchant:

1. Exact normalized merchant mapping already approved in the local database.
2. Previously approved alias or unambiguous canonical merchant-family decision.
3. Reliable provider category as supporting evidence.
4. Online merchant research only when explicitly requested and no approved local
   answer exists.
5. Manual review for ambiguous, contradictory, or low-confidence results.

An online name match or provider category must never overwrite an exact approved
database mapping automatically.

If online research is authorized, send only the merchant name needed for the
lookup. Never send card details, transaction amounts, dates, income, notes, or a
complete transaction history. Store user-approved results locally.

When present, `data/category-policy.json` is a local source of user-approved
classification policy. Do not overwrite it or publish it without review.

## Three independent decisions

### Permanent merchant category

Stored in `merchant_mappings` and keyed by exact normalized merchant name. It
updates matching historical transactions and applies to future exact matches.

### Display identity

Stored in `merchant_display_mappings`. It provides the clean name used for
grouping and presentation while preserving every original statement description.

Several aliases may share one display identity while retaining different
permanent categories. Grouping a brand must never force all aliases into one
category.

### Transaction-specific override

Stored in `transaction_category_overrides`. It changes one exceptional
transaction without changing the merchant rule or future imports.

The UI must make the scope explicit before saving: one transaction, an exact
merchant alias, or another supported permanent scope. Never infer a broader
scope from a one-row action.

## Manual-review behavior

- `Needs review` is a valid safe state.
- Do not invent a permanent category merely to complete an import.
- Show the proposed category, display name, match source, scope, and impact.
- Preserve existing reviewed decisions when new evidence conflicts.
- Apply bulk category or display-name changes only after a backup and explicit
  approval.

## Provider-specific information

Normalize shared fields while preserving provider-specific details in the raw
source payload. Additional fields may be important for future auditing and must
not be discarded simply because another provider does not supply them.
