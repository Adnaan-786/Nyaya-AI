"""
FixtureProvider: keyword search over a small synthetic case-law corpus
in app/fixtures/indian_kanoon_fixtures.json. Used whenever
settings.indian_kanoon_provider == "fixture" (the default), so the
whole researcher pipeline -- retrieval, re-rank, generation, citation
verification -- can run and be tested fully offline, same philosophy
as module M5's eCourts FixtureProvider.

The fixture corpus is explicitly synthetic/illustrative (see the
"_note" field in the JSON file) -- not real case law, not real
citations.
"""

import json
from pathlib import Path

from app.integrations.indian_kanoon.base import IndianKanoonProvider, KanoonResult

FIXTURES_PATH = (
    Path(__file__).resolve().parents[2] / "fixtures" / "indian_kanoon_fixtures.json"
)


def _load_fixtures() -> list[dict]:
    with open(FIXTURES_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return data["cases"]


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
        cases = _load_fixtures()
        query_terms = {t for t in query.lower().split() if len(t) > 2}

        if not query_terms:
            scored = [(0, entry) for entry in cases]
        else:
            scored = [(_score(query_terms, entry), entry) for entry in cases]

        scored.sort(key=lambda pair: pair[0], reverse=True)
        # Only return entries with at least some keyword overlap, so an
        # unrelated query legitimately yields few/no results (exercises
        # the "insufficient confidence" path in researcher.py).
        relevant = [entry for score, entry in scored if score > 0]

        return [_to_result(entry) for entry in relevant[:top_k]]

    async def fetch_document(self, doc_id: str) -> KanoonResult | None:
        for entry in _load_fixtures():
            if entry["doc_id"] == doc_id:
                return _to_result(entry)
        return None
