from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class ReviewedReimbursement:
    reimbursed_amount: float
    adjustment_type: str
    personal_amount: float


def personal_spending_amount(
    charged_amount: float,
    reimbursed_amount: float = 0.0,
) -> float:
    """Return the positive card charge that belongs to personal spending."""
    if charged_amount <= 0:
        return 0.0
    return max(charged_amount - reimbursed_amount, 0.0)


def review_reimbursement(
    charged_amount: float,
    reimbursed_amount: float,
) -> ReviewedReimbursement:
    """Validate and normalize a reviewed reimbursement decision."""
    if charged_amount <= 0:
        raise ValueError("Only positive card charges can be marked as reimbursed")
    if not math.isfinite(reimbursed_amount) or reimbursed_amount <= 0:
        raise ValueError("Reimbursed amount must be greater than zero")
    if reimbursed_amount > charged_amount + 0.005:
        raise ValueError("Reimbursed amount cannot exceed the original card charge")
    normalized = round(min(reimbursed_amount, charged_amount), 2)
    adjustment_type = (
        "full_reimbursement"
        if abs(normalized - charged_amount) < 0.005
        else "partial_reimbursement"
    )
    return ReviewedReimbursement(
        reimbursed_amount=normalized,
        adjustment_type=adjustment_type,
        personal_amount=round(
            personal_spending_amount(charged_amount, normalized), 2
        ),
    )


def personal_spending_sql(alias: str = "t") -> str:
    """SQLite expression equivalent to :func:`personal_spending_amount`."""
    prefix = f"{alias}." if alias else ""
    return (
        f"CASE WHEN CAST({prefix}charged_amount AS REAL)>0 THEN "
        f"MAX(CAST({prefix}charged_amount AS REAL)-COALESCE((SELECT "
        "CAST(adjustment.reimbursed_amount AS REAL) FROM "
        "transaction_spending_adjustments adjustment "
        f"WHERE adjustment.transaction_id={prefix}id),0),0) ELSE 0 END"
    )
