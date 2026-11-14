"""Unified read-only workflow for monthly and historical observations."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from clearspend.observations.grouping import (
    ObservationFinding,
    ObservationGroup,
    active_observation_findings,
)
from clearspend.observations.historical_analysis import analyze_historical_observations
from clearspend.observations.historical_inputs import historical_dataset_from_snapshot
from clearspend.observations.historical_presentation import (
    historical_findings,
    historical_observation_groups,
)
from clearspend.observations.inputs import (
    ObservationInputSnapshot,
    load_observation_inputs,
)
from clearspend.observations.monthly_analysis import analyze_monthly_observations
from clearspend.observations.monthly_inputs import monthly_dataset_from_snapshot
from clearspend.observations.monthly_presentation import (
    monthly_findings,
    monthly_observation_groups,
)


@dataclass(frozen=True)
class ObservationView:
    period: str
    selected_card: str
    selected_month: str
    observed_start: str
    observed_end: str
    findings: tuple[ObservationFinding, ...]
    groups: tuple[ObservationGroup, ...]

    @property
    def historical(self) -> bool:
        return self.period != "month"

    @property
    def finding_count(self) -> int:
        return len(self.findings)

    @property
    def type_count(self) -> int:
        return len(self.groups)


def observation_view_from_snapshot(
    snapshot: ObservationInputSnapshot,
) -> ObservationView:
    """Analyze one assembled snapshot through the correct period boundary."""
    reviewed = tuple(snapshot.reviewed_finding_keys)
    if snapshot.scope.historical:
        dataset = historical_dataset_from_snapshot(snapshot)
        analysis = analyze_historical_observations(dataset)
        all_findings = historical_findings(analysis)
        groups = historical_observation_groups(analysis, reviewed)
    else:
        dataset = monthly_dataset_from_snapshot(snapshot)
        analysis = analyze_monthly_observations(dataset)
        all_findings = monthly_findings(analysis, dataset)
        groups = monthly_observation_groups(analysis, dataset, reviewed)
    findings = active_observation_findings(all_findings, reviewed)
    return ObservationView(
        period=snapshot.scope.period,
        selected_card=snapshot.selected_card,
        selected_month=snapshot.scope.selected_month,
        observed_start=snapshot.scope.observed_start,
        observed_end=snapshot.scope.observed_end,
        findings=findings,
        groups=groups,
    )


def load_observation_view(
    database: Path,
    *,
    period: str,
    card: str,
    month: str = "",
    income_hidden: bool = False,
) -> ObservationView:
    """Load and analyze observations without exposing a route or performing writes."""
    return observation_view_from_snapshot(load_observation_inputs(
        database,
        period=period,
        card=card,
        month=month,
        income_hidden=income_hidden,
    ))
