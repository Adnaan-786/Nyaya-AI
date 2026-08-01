"""
FixtureProvider: serves recorded eCourts data from
app/fixtures/ecourts_fixtures.json. Used whenever
settings.ecourts_provider == "fixture" (the default), so the whole
stack -- including the sync worker and IC-1 checkpoint -- can run
fully offline and deterministically (plan C.2, C.7 DoD).

Three of the 25 seeded CNRs are "mutable": calling
`trigger_fixture_mutation()` (wired to a small CLI script) flips them
to a changed state (new stage / next_hearing_date / an extra history
entry) so the diff-detection + notification pipeline can be exercised
on staging exactly as described in C.7's Definition of Done.
"""

import datetime
import json
from pathlib import Path

from app.integrations.ecourts.base import (
    ECourtsProvider,
    ECourtsProviderError,
    NormalizedCase,
    NormalizedHearing,
)

FIXTURES_PATH = Path(__file__).resolve().parents[2] / "fixtures" / "ecourts_fixtures.json"
MUTATION_MARKER_PATH = Path(__file__).resolve().parents[2] / "fixtures" / ".mutation_triggered"


def trigger_fixture_mutation() -> None:
    """Flips the 3 mutable fixture CNRs into their 'changed' state."""
    MUTATION_MARKER_PATH.write_text("triggered")


def reset_fixture_mutation() -> None:
    """Reverts fixtures to their original state (useful between test runs)."""
    MUTATION_MARKER_PATH.unlink(missing_ok=True)


def _load_fixtures() -> dict:
    with open(FIXTURES_PATH) as f:
        return json.load(f)


def _mutation_active() -> bool:
    return MUTATION_MARKER_PATH.exists()


def _to_normalized(raw_case: dict) -> NormalizedCase:
    history = [
        NormalizedHearing(
            date=datetime.date.fromisoformat(h["date"]),
            purpose=h.get("purpose"),
            outcome_notes=h.get("outcome_notes"),
        )
        for h in raw_case.get("history", [])
    ]

    return NormalizedCase(
        cnr=raw_case["cnr"],
        title=raw_case["title"],
        court_name=raw_case.get("court_name"),
        court_type=raw_case.get("court_type"),
        judge_name=raw_case.get("judge_name"),
        case_type=raw_case.get("case_type"),
        stage=raw_case.get("stage"),
        parties=raw_case.get("parties", []),
        next_hearing_date=(
            datetime.date.fromisoformat(raw_case["next_hearing_date"])
            if raw_case.get("next_hearing_date")
            else None
        ),
        history=history,
        raw=raw_case,
    )


class FixtureProvider(ECourtsProvider):
    async def lookup_cnr(self, cnr: str) -> NormalizedCase:
        fixtures = _load_fixtures()
        raw_case = fixtures["cases"].get(cnr)

        if raw_case is None:
            raise ECourtsProviderError(f"No fixture data for CNR {cnr!r}.")

        raw_case = dict(raw_case)

        if _mutation_active() and cnr in fixtures.get("mutations", {}):
            mutation = fixtures["mutations"][cnr]
            raw_case["stage"] = mutation["stage"]
            raw_case["next_hearing_date"] = mutation["next_hearing_date"]
            raw_case = dict(raw_case)
            raw_case["history"] = [*raw_case.get("history", []), mutation["new_history_entry"]]

        return _to_normalized(raw_case)

    async def case_status(self, cnr: str) -> NormalizedCase:
        return await self.lookup_cnr(cnr)

    async def cause_list(self, court_id: str, date: datetime.date) -> list[NormalizedCase]:
        fixtures = _load_fixtures()
        results = []
        for raw_case in fixtures["cases"].values():
            if raw_case.get("court_name") == court_id:
                results.append(_to_normalized(raw_case))
        return results
