"""Period and history scope selection for financial observations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class ObservationScope:
    period: str
    selected_month: str
    scope_start: str
    scope_end: str
    target_months: tuple[str, ...]
    history_months: tuple[str, ...]
    recurring_months: tuple[str, ...]
    observed_start: str
    observed_end: str

    @property
    def historical(self) -> bool:
        return self.period != "month"


def build_observation_scope(
    *,
    period: str,
    available_months: Iterable[str],
    selected_month: str = "",
    period_start: str = "",
    period_end: str = "",
) -> ObservationScope:
    """Reproduce the established current-period and historical lookback scopes."""
    available = tuple(sorted(dict.fromkeys(
        month for month in available_months if month
    )))
    fallback_month = period_start[:7]
    selected = selected_month or fallback_month
    scope_start = period_start[:7]
    scope_end = period_end[:7] or selected
    if period == "month":
        target = (selected,) if selected else ()
    else:
        target = tuple(
            month for month in available if scope_start <= month <= scope_end
        )
    history = tuple(month for month in available if month <= scope_end)
    recurring = target if period == "month" else history
    observed_start = target[0] if target else scope_start
    observed_end = target[-1] if target else scope_end
    return ObservationScope(
        period=period,
        selected_month=selected,
        scope_start=scope_start,
        scope_end=scope_end,
        target_months=target,
        history_months=history,
        recurring_months=recurring,
        observed_start=observed_start,
        observed_end=observed_end,
    )
