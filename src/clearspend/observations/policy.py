"""Shared policy for reversible financial-observation review decisions."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ObservationReviewPolicy:
    observation_type: str
    resolution: str
    action_label: str
    resolved_label: str
    activity_label: str
    activity_target: str
    minimum_transactions: int
    maximum_transactions: int | None = None
    requires_recurring_series: bool = False

    def accepts_transaction_count(self, count: int) -> bool:
        return (
            count >= self.minimum_transactions
            and (self.maximum_transactions is None or count <= self.maximum_transactions)
        )


OBSERVATION_REVIEW_POLICIES: dict[str, ObservationReviewPolicy] = {
    "POSSIBLE DUPLICATE": ObservationReviewPolicy(
        observation_type="POSSIBLE DUPLICATE",
        resolution="not_duplicate",
        action_label="Not duplicate",
        resolved_label="Marked as not a duplicate",
        activity_label="Open transactions",
        activity_target="transactions",
        minimum_transactions=2,
    ),
    "ADDITIONAL RECURRING CHARGE": ObservationReviewPolicy(
        observation_type="ADDITIONAL RECURRING CHARGE",
        resolution="expected_charge",
        action_label="Expected charge",
        resolved_label="Marked as an expected separate charge",
        activity_label="Open recurring series",
        activity_target="recurring_series",
        minimum_transactions=2,
        requires_recurring_series=True,
    ),
    "UNUSUAL TRANSACTION": ObservationReviewPolicy(
        observation_type="UNUSUAL TRANSACTION",
        resolution="not_unusual",
        action_label="Not unusual",
        resolved_label="Marked as expected / not unusual",
        activity_label="Open transaction",
        activity_target="transaction",
        minimum_transactions=1,
        maximum_transactions=1,
    ),
}

OBSERVATION_RESOLUTIONS = {
    observation_type: policy.resolution
    for observation_type, policy in OBSERVATION_REVIEW_POLICIES.items()
}


def observation_review_policy(
    observation_type: str,
) -> ObservationReviewPolicy | None:
    """Return review behavior for a type, or None for factual observations."""
    return OBSERVATION_REVIEW_POLICIES.get(str(observation_type).strip().upper())
