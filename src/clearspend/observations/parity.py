"""Compare browser and backend observation payloads at explicit parity tiers."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable


def _ids(item: dict) -> tuple[int, ...]:
    return tuple(sorted(int(value) for value in (item.get("transactionIds") or ())))


def finding_identity(item: dict) -> tuple[str, str, str, str, tuple[int, ...]]:
    """Return qualification identity without presentation text or score."""
    return (
        str(item.get("type") or ""),
        str(item.get("month") or ""),
        str(item.get("label") or ""),
        str(item.get("findingKey") or ""),
        _ids(item),
    )


def _freeze(value: object) -> object:
    if isinstance(value, dict):
        return tuple(sorted((str(key), _freeze(item)) for key, item in value.items()))
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


def _presentation(item: dict) -> tuple[object, ...]:
    """Compare the complete browser-compatible finding, including action metadata."""
    return (_freeze(item),)


def _counter(values: Iterable[tuple]) -> Counter:
    return Counter(values)


def _expanded(counter: Counter) -> tuple[tuple, ...]:
    return tuple(sorted(counter.elements(), key=repr))


@dataclass(frozen=True)
class ObservationParityReport:
    browser_finding_count: int
    backend_finding_count: int
    browser_only_findings: tuple[tuple, ...]
    backend_only_findings: tuple[tuple, ...]
    browser_group_types: tuple[str, ...]
    backend_group_types: tuple[str, ...]
    presentation_difference_count: int

    @property
    def qualification_matches(self) -> bool:
        return not self.browser_only_findings and not self.backend_only_findings

    @property
    def grouping_matches(self) -> bool:
        return self.browser_group_types == self.backend_group_types

    @property
    def presentation_matches(self) -> bool:
        return self.presentation_difference_count == 0


def compare_observation_payloads(
    browser: dict,
    backend: dict,
) -> ObservationParityReport:
    """Compare qualification, grouping and presentation independently."""
    browser_findings = tuple(browser.get("findings") or ())
    backend_findings = tuple(backend.get("findings") or ())
    browser_identities = _counter(finding_identity(item) for item in browser_findings)
    backend_identities = _counter(finding_identity(item) for item in backend_findings)
    browser_presentations = _counter(_presentation(item) for item in browser_findings)
    backend_presentations = _counter(_presentation(item) for item in backend_findings)
    presentation_difference_count = sum(
        (browser_presentations - backend_presentations).values()
    ) + sum((backend_presentations - browser_presentations).values())
    return ObservationParityReport(
        browser_finding_count=len(browser_findings),
        backend_finding_count=len(backend_findings),
        browser_only_findings=_expanded(browser_identities - backend_identities),
        backend_only_findings=_expanded(backend_identities - browser_identities),
        browser_group_types=tuple(
            str(group.get("type") or "") for group in (browser.get("groups") or ())
        ),
        backend_group_types=tuple(
            str(group.get("type") or "") for group in (backend.get("groups") or ())
        ),
        presentation_difference_count=presentation_difference_count,
    )
