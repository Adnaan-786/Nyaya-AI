"""Keyword search over a small synthetic corpus, so the researcher runs with no key.

The default whenever `INDIANKANOON_API_KEY` is unset, which lets the whole pipeline —
retrieval, generation, citation verification — be exercised end to end offline, the
same way the eCourts fixtures work.

The corpus is explicitly synthetic (see `_note` in the JSON, and the "(Fixture)" suffix
on every case title): illustrative entries with `fixtures.local` URLs, not real
judgments. Nothing here may be presented to a lawyer as authority, which is why
`app/api/ai.py` does not route the live research endpoint through this provider.
"""

import json
from pathlib import Path

from app.integrations.indian_kanoon.base import IndianKanoonProvider, KanoonResult

FIXTURES_PATH = Path(__file__).resolve().parents[2] / "fixtures" / "indian_kanoon_fixtures.json"


def _load_fixtures() -> list[dict]:
    with open(FIXTURES_PATH, encoding="utf-8") as handle:
        return json.load(handle)["cases"]


def _to_result(entry: dict) -> KanoonResult:
    return KanoonResult(
        doc_id=entry["doc_id"],
        case_title=entry["case_title"],
        court=entry["court"],
        year=entry["year"],
        source_url=entry["source_url"],
        snippet=entry["snippet"],
    )


def _score(query_terms: set[str], entry: dict) -> int:
    haystack = " ".join(
        [entry["case_title"], entry["snippet"], " ".join(entry.get("topics", []))]
    ).lower()
    return sum(1 for term in query_terms if term in haystack)


class FixtureProvider(IndianKanoonProvider):
    async def search(self, query: str, *, top_k: int) -> list[KanoonResult]:
        query_terms = {t for t in query.lower().split() if len(t) > 2}
        scored = [(_score(query_terms, entry), entry) for entry in _load_fixtures()]
        scored.sort(key=lambda pair: pair[0], reverse=True)

        # Only entries with real keyword overlap, so an unrelated query genuinely
        # returns nothing and exercises the insufficient-confidence path rather than
        # handing the model twenty irrelevant fragments to pick from.
        relevant = [entry for score, entry in scored if score > 0]
        return [_to_result(entry) for entry in relevant[:top_k]]

    async def fetch_document(self, doc_id: str) -> KanoonResult | None:
        for entry in _load_fixtures():
            if entry["doc_id"] == doc_id:
                return _to_result(entry)
        return None
