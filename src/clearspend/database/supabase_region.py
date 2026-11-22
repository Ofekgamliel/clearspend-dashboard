"""Validation helpers for region-qualified Supabase pooler endpoints."""

from __future__ import annotations

import re


_REGION_PATTERN = re.compile(r"[a-z]{2}(?:-[a-z0-9]+)+-\d")
_POOLER_HOST_PATTERN = re.compile(
    r"aws-\d+-(?P<region>[a-z]{2}(?:-[a-z0-9]+)+-\d)"
    r"\.pooler\.supabase\.com"
)


def validated_supabase_pooler_region(host: str, expected_region: str) -> str:
    """Return the pooler region or reject an unverifiable/mismatched endpoint."""
    normalized_host = host.strip().lower()
    normalized_expected = expected_region.strip().lower()
    if not _REGION_PATTERN.fullmatch(normalized_expected):
        raise ValueError("expected_region must be a valid region identifier")
    match = _POOLER_HOST_PATTERN.fullmatch(normalized_host)
    if match is None:
        raise ValueError(
            "host must be a region-qualified Supabase Session-pooler endpoint"
        )
    actual_region = match.group("region")
    if actual_region != normalized_expected:
        raise ValueError("host region does not match expected_region")
    return actual_region
