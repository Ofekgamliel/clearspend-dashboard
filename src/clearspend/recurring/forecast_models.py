"""Typed evidence and internal occurrence models for Upcoming forecasts."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TypedDict


@dataclass(frozen=True)
class ChargeEvidence:
    transaction_key: str
    report_month: str
    amount: Decimal
    provider: str
    card_last4: str
    transaction_date: str | None = None
    billing_date: str | None = None
    charged_currency: str | None = None
    installment_number: int | None = None
    installment_total: int | None = None

    @property
    def card(self) -> str:
        return f"{self.provider}:{self.card_last4}"


@dataclass(frozen=True)
class RecurringForecastEvidence:
    profile_id: str
    display_name: str
    recurring_type: str
    cadence: str
    lifecycle_status: str
    end_month: str | None
    charges: tuple[ChargeEvidence, ...]


@dataclass(frozen=True)
class InstallmentForecastEvidence:
    commitment_id: str
    display_name: str
    charges: tuple[ChargeEvidence, ...]


class InternalOccurrence(TypedDict):
    occurrence_id: str
    expected_date: str | None
    date_evidence: str
    display_name: str
    card: dict[str, str]
    payment_type: str
    amount: float | None
    amount_evidence: str
    amount_confidence: str | None
    occurrence_status: str
    recent_range: list[float] | None
    installment_number: int | None
    installment_total: int | None
    annual: bool
    ending: bool
    _month: str
    _logical_card: str


class UnresolvedForecast(TypedDict):
    source_kind: str
    source_id: str
    display_name: str
    card: dict[str, str] | None
    reason: str
