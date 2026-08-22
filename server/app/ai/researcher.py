"""C.9 retrieval-grounded case-law research.

Four steps: normalise the query, retrieve candidate judgments from Indian Kanoon, have
the model answer *only* from those fragments, then verify every citation it leaned on
before any of them reach a lawyer.

The safety property this whole module exists for: **citation metadata never comes from
the model.** The model is shown numbered fragments and returns fragment indices plus a
relevance note; case title, court, year and URL are copied back out of our own
retrieval data. A case name the model invented has no path into the result, because
there is no field for it to arrive in. `app/integrations/llm.py`'s
`research_case_law` is the other, weaker shape — it asks the model to recall citations
and then drops the ones that cannot be verified — and that is the path the live
`/ai/research` endpoint still uses while the only corpus available here is synthetic.
"""

import logging

import httpx

from app.ai.parsing import parse_json_object
from app.ai.prompts import build_research_generation_prompt
from app.ai.query_normalizer import normalize_query
from app.integrations import indian_kanoon
from app.integrations.indian_kanoon import IndianKanoonProviderError, KanoonResult
from app.integrations.llm import complete

logger = logging.getLogger(__name__)

# How many candidates to pull, and how many of those to actually put in front of the
# model. The gap is where semantic re-ranking belongs; until embeddings land this is a
# plain truncation of the provider's own relevance ordering, so keep the two close.
RETRIEVE_TOP_K = 20
RERANK_TOP_K = 6

# Below this many *verified* citations the answer is withheld entirely. Two rather than
# one because a single authority is exactly the case where a lawyer is most likely to
# rely on it without checking.
MIN_VERIFIED_CITATIONS = 2

# Beyond which point more verified authority stops meaning more confidence.
HIGH_CONFIDENCE_CITATIONS = 4

URL_CHECK_TIMEOUT_SECONDS = 5

INSUFFICIENT_MESSAGE = (
    "No reliable authority could be found to confidently answer this query. "
    "Please consult a full-text legal database or a colleague for verification."
)

# Coverage of subordinate courts is genuinely thinner than of the High Courts and the
# Supreme Court, so an answer to a district-court question carries a caveat rather than
# implying the search was exhaustive.
_DISTRICT_COURT_TERMS = ("district court", "sessions court", "magistrate", "civil judge")

_SPARSE_COVERAGE_NOTE = (
    "\n\n*Note: case-law coverage is sparser for district and subordinate courts than "
    "for High Courts and the Supreme Court; please verify against a full-text database "
    "for district-level matters.*"
)


def _looks_like_valid_url(url: str) -> bool:
    return url.startswith(("http://", "https://"))


async def _verify_url_resolves(url: str) -> bool:
    """B.11: a citation is only usable if its `source_url` actually resolves.

    Against the fixture corpus there is nothing to resolve — the URLs are
    `fixtures.local` by design — so the check degrades to well-formedness there and
    becomes a real HTTP request the moment a real provider is configured.
    """
    if not _looks_like_valid_url(url):
        return False

    if not indian_kanoon.is_live():
        return True

    try:
        async with httpx.AsyncClient(
            timeout=URL_CHECK_TIMEOUT_SECONDS, follow_redirects=True
        ) as client:
            response = await client.head(url)
            return response.status_code < 400
    except httpx.HTTPError:
        return False


async def _retrieve(english_query: str) -> list[KanoonResult]:
    provider = indian_kanoon.get_indian_kanoon_provider()

    try:
        candidates = await provider.search(english_query, top_k=RETRIEVE_TOP_K)
    except IndianKanoonProviderError:
        # An unreachable index means nothing was verified, which the caller turns into
        # `insufficient`. It must never mean "answer from memory instead".
        logger.warning("indian kanoon search failed for %r", english_query)
        return []

    return candidates[:RERANK_TOP_K]


async def _generate_answer(query: str, fragments: list[KanoonResult], language: str) -> dict:
    fragment_payload = [
        {
            "index": i + 1,
            "case_title": fragment.case_title,
            "court": fragment.court,
            "year": fragment.year,
            "snippet": fragment.snippet,
        }
        for i, fragment in enumerate(fragments)
    ]

    system, user = build_research_generation_prompt(query, fragment_payload, language=language)
    raw = await complete(system=system, user=user, json_mode=True)
    return parse_json_object(raw, task="research_generate")


async def _verify_citations(
    model_citations: list, fragments: list[KanoonResult]
) -> list[dict]:
    """Confirm each cited document still exists in the index and its URL resolves.

    Everything but `relevance_note` is copied from the fragment, not from the model's
    reply — the model only gets to say *which* fragment it used and why.
    """
    provider = indian_kanoon.get_indian_kanoon_provider()
    verified: list[dict] = []

    for citation in model_citations:
        if not isinstance(citation, dict):
            continue

        index = citation.get("fragment_index")
        if not isinstance(index, int) or not 1 <= index <= len(fragments):
            continue

        fragment = fragments[index - 1]

        try:
            fetched = await provider.fetch_document(fragment.doc_id)
        except IndianKanoonProviderError:
            fetched = None

        if fetched is None:
            logger.warning("citation dropped: document %s not found", fragment.doc_id)
            continue

        if not await _verify_url_resolves(fragment.source_url):
            logger.warning("citation dropped: url did not resolve for %s", fragment.doc_id)
            continue

        verified.append(
            {
                "case_title": fragment.case_title,
                "court": fragment.court,
                "year": fragment.year,
                "source_url": fragment.source_url,
                "relevance_note": citation.get("relevance_note") or "",
            }
        )

    return verified


def _confidence_for(verified_count: int) -> str:
    if verified_count < MIN_VERIFIED_CITATIONS:
        return "insufficient"
    if verified_count >= HIGH_CONFIDENCE_CITATIONS:
        return "high"
    return "medium"


def _insufficient() -> dict:
    return {
        "answer_markdown": INSUFFICIENT_MESSAGE,
        "citations": [],
        "confidence": "insufficient",
    }


async def research(*, query: str, language: str = "en") -> dict:
    """The B.7 `research` result shape: answer_markdown, citations, confidence."""
    normalized = await normalize_query(query)
    fragments = await _retrieve(normalized["english_query"])

    if not fragments:
        return _insufficient()

    generated = await _generate_answer(query, fragments, language)
    verified_citations = await _verify_citations(generated.get("citations") or [], fragments)

    if _confidence_for(len(verified_citations)) == "insufficient":
        # The answer text is discarded along with the citations. Keeping a
        # confident-sounding paragraph and only emptying the citation list is how an
        # unsupported proposition gets carried into court.
        return _insufficient()

    answer_markdown = generated.get("answer_markdown") or ""
    if not answer_markdown.strip():
        return _insufficient()

    if any(term in query.lower() for term in _DISTRICT_COURT_TERMS):
        answer_markdown += _SPARSE_COVERAGE_NOTE

    return {
        "answer_markdown": answer_markdown,
        "citations": verified_citations,
        "confidence": _confidence_for(len(verified_citations)),
    }
