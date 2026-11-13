from __future__ import annotations

import json
import subprocess
from pathlib import Path

from clearspend.observations.inputs import ObservationInputSnapshot


ROOT = Path(__file__).resolve().parents[2]
RUNNER = Path(__file__).with_name("browser_observations_reference.mjs")


def browser_observation_payload(snapshot: ObservationInputSnapshot) -> dict:
    """Run the tracked production browser engine against one safe snapshot."""
    request = {
        "period": snapshot.scope.period,
        "targetMonths": list(snapshot.scope.target_months),
        "historyMonths": list(snapshot.scope.history_months),
        "recurringMonths": list(snapshot.scope.recurring_months),
        "transactionsByMonth": {
            month: list(rows) for month, rows in snapshot.transactions_by_month.items()
        },
        "recurringByMonth": snapshot.recurring_by_month,
        "householdHistory": snapshot.household_history,
        "partialMonth": snapshot.partial_month,
        "incomeVisible": snapshot.income_visible,
        "reviewedFindingKeys": list(snapshot.reviewed_finding_keys),
    }
    completed = subprocess.run(
        (
            "node",
            str(RUNNER),
            str(ROOT / "dist" / "observations.js"),
            str(ROOT / "dist" / "format.js"),
        ),
        input=json.dumps(request),
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(completed.stdout)
