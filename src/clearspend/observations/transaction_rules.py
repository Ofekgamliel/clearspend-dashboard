"""Pure transaction-level qualification rules for financial observations.

These functions mirror the established browser rules without opening SQLite or
constructing presentation text. They are not wired into the HTTP API yet; the
legacy observation engine remains authoritative until full payload parity is
proved.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import Iterable

from clearspend.reporting.periods import shift_month


LARGE_PURCHASE_MINIMUM = 500.0
LARGE_PURCHASE_SHARE = 0.075
STABLE_HISTORY_PURCHASES = 5
STABLE_HISTORY_MONTHS = 3
STABLE_HISTORY_BAND = 0.30
STABLE_HISTORY_FRACTION = 0.75
UNUSUAL_MULTIPLIER = 2.5
UNUSUAL_MINIMUM_DIFFERENCE = 100.0


@dataclass(frozen=True)
class ObservationTransaction:
    id: int
    merchant_normalized: str
    canonical_merchant_id: str
    category: str
    provider: str
    card_last4: str
    transaction_date: str
    month: str
    charged_amount: float
    charged_currency: str
    personal_amount: float
    installment_total: int | None = None

    @property
    def identity(self) -> tuple[str, str]:
        return (self.canonical_merchant_id or self.merchant_normalized, self.category)


@dataclass(frozen=True)
class DuplicateCandidate:
    transaction_ids: tuple[int, ...]
    charged_amount: float

    @property
    def finding_key(self) -> str:
        return duplicate_review_key(self.transaction_ids)


@dataclass(frozen=True)
class StablePurchaseBaseline:
    median: float
    purchase_count: int
    month_count: int
    inside_band_count: int


@dataclass(frozen=True)
class PurchaseSignal:
    transaction_id: int
    observation_type: str
    amount: float
    monthly_total: float
    monthly_share: float
    baseline: StablePurchaseBaseline | None
    ratio_to_median: float

    @property
    def finding_key(self) -> str | None:
        return (
            unusual_review_key(self.transaction_id)
            if self.observation_type == "UNUSUAL TRANSACTION"
            else None
        )


def _median(values: Iterable[float]) -> float:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return 0.0
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def duplicate_review_key(transaction_ids: Iterable[int]) -> str:
    ids = sorted({int(value) for value in transaction_ids})
    return f"POSSIBLE DUPLICATE:{','.join(str(value) for value in ids)}"


def unusual_review_key(transaction_id: int) -> str:
    return f"UNUSUAL TRANSACTION:{int(transaction_id)}"


def possible_duplicate_groups(
    transactions: Iterable[ObservationTransaction],
) -> tuple[DuplicateCandidate, ...]:
    """Find exact charge candidates without deleting or merging transactions."""
    groups: dict[tuple[str, str, str, str, str, str], list[ObservationTransaction]] = {}
    for transaction in transactions:
        if transaction.personal_amount <= 0 or transaction.installment_total:
            continue
        key = (
            transaction.merchant_normalized,
            transaction.provider,
            transaction.card_last4,
            transaction.transaction_date,
            f"{transaction.charged_amount:.2f}",
            transaction.charged_currency,
        )
        groups.setdefault(key, []).append(transaction)
    candidates = [
        DuplicateCandidate(
            transaction_ids=tuple(sorted(transaction.id for transaction in group)),
            charged_amount=group[0].charged_amount,
        )
        for group in groups.values()
        if len(group) > 1
    ]
    return tuple(sorted(candidates, key=lambda candidate: candidate.transaction_ids))


def stable_purchase_baseline(
    history: Iterable[ObservationTransaction],
) -> StablePurchaseBaseline | None:
    """Return the established six-month eligibility baseline, if reliable."""
    rows = [transaction for transaction in history if transaction.personal_amount > 0]
    if len(rows) < STABLE_HISTORY_PURCHASES:
        return None
    month_count = len({transaction.month for transaction in rows})
    if month_count < STABLE_HISTORY_MONTHS:
        return None
    typical = _median(transaction.personal_amount for transaction in rows)
    if typical <= 0:
        return None
    inside = sum(
        abs(transaction.personal_amount - typical) <= typical * STABLE_HISTORY_BAND
        for transaction in rows
    )
    if inside < ceil(len(rows) * STABLE_HISTORY_FRACTION):
        return None
    return StablePurchaseBaseline(
        median=round(typical, 2),
        purchase_count=len(rows),
        month_count=month_count,
        inside_band_count=inside,
    )


def prior_identity_purchases(
    candidate: ObservationTransaction,
    transactions: Iterable[ObservationTransaction],
) -> tuple[ObservationTransaction, ...]:
    """Select the candidate's positive purchases from the previous six months."""
    history_start = shift_month(candidate.month, -6)
    return tuple(
        transaction
        for transaction in transactions
        if transaction.id != candidate.id
        and transaction.identity == candidate.identity
        and history_start <= transaction.month < candidate.month
        and transaction.personal_amount > 0
    )


def purchase_signal(
    candidate: ObservationTransaction,
    transactions: Iterable[ObservationTransaction],
    *,
    monthly_positive_personal_spending: float,
    merchant_activity_already_changed: bool = False,
) -> PurchaseSignal | None:
    """Classify one eligible non-recurring, non-duplicate purchase.

    Orchestration is responsible for excluding reviewed recurring charges and
    possible duplicate candidates before calling this function.
    """
    amount = candidate.personal_amount
    if amount <= 0:
        return None
    monthly_total = float(monthly_positive_personal_spending)
    share = amount / monthly_total if monthly_total > 0 else 0.0
    large = amount >= LARGE_PURCHASE_MINIMUM and share >= LARGE_PURCHASE_SHARE
    baseline = stable_purchase_baseline(prior_identity_purchases(candidate, transactions))
    ratio = amount / baseline.median if baseline and baseline.median else 0.0
    unusual = bool(
        baseline
        and ratio >= UNUSUAL_MULTIPLIER
        and amount - baseline.median >= UNUSUAL_MINIMUM_DIFFERENCE
        and not merchant_activity_already_changed
    )
    if not large and not unusual:
        return None
    observation_type = (
        "LARGE AND UNUSUAL PURCHASE"
        if large and unusual
        else "LARGE PURCHASE" if large else "UNUSUAL TRANSACTION"
    )
    return PurchaseSignal(
        transaction_id=candidate.id,
        observation_type=observation_type,
        amount=round(amount, 2),
        monthly_total=round(monthly_total, 2),
        monthly_share=round(share, 6),
        baseline=baseline,
        ratio_to_median=round(ratio, 6),
    )
