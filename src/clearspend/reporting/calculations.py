from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class IncomeBalance:
    income: float
    spending: float
    charges: float
    refunds: float
    remaining: float
    remaining_percentage: float | None
    spent_percentage: float | None


@dataclass(frozen=True)
class MonthlyAverages:
    spending: float
    amount_left: float | None
    spending_months: int
    amount_left_months: int
    start_month: str | None
    end_month: str | None
    current_month_partial: bool


def calculate_income_balance(
    *,
    income: float,
    personal_positive_spending: float,
    gross_charges: float,
    refunds: float,
) -> IncomeBalance:
    """Calculate household spending after reimbursements and card refunds."""
    net_spending = personal_positive_spending - refunds
    remaining = income - net_spending
    return IncomeBalance(
        income=round(income, 2),
        spending=round(net_spending, 2),
        charges=round(gross_charges, 2),
        refunds=round(refunds, 2),
        remaining=round(remaining, 2),
        remaining_percentage=round(remaining / income * 100, 1) if income else None,
        spent_percentage=round(net_spending / income * 100, 1) if income else None,
    )


def calculate_monthly_averages(
    monthly_spending: Mapping[str, float],
    monthly_income: Mapping[str, float],
    *,
    current_month: str,
) -> MonthlyAverages:
    """Calculate averages using the same covered-month rules as the dashboard.

    Spending uses months containing spending records. Amount left uses months
    containing income and treats a missing spending record in such a month as
    zero spending.
    """
    average_spending = (
        sum(monthly_spending.values()) / len(monthly_spending)
        if monthly_spending else 0.0
    )
    monthly_amounts_left = [
        total - monthly_spending.get(month, 0.0)
        for month, total in monthly_income.items()
    ]
    average_amount_left = (
        sum(monthly_amounts_left) / len(monthly_amounts_left)
        if monthly_amounts_left else None
    )
    covered_months = sorted(set(monthly_spending) | set(monthly_income))
    return MonthlyAverages(
        spending=round(average_spending, 2),
        amount_left=round(average_amount_left, 2) if average_amount_left is not None else None,
        spending_months=len(monthly_spending),
        amount_left_months=len(monthly_amounts_left),
        start_month=covered_months[0] if covered_months else None,
        end_month=covered_months[-1] if covered_months else None,
        current_month_partial=current_month in covered_months,
    )
