import json
import math
import re

from app.ai.prompts import build_research_generation_prompt
from app.ai.query_normalizer import normalize_query
from app.config import get_settings
from app.core.logging import get_logger
from app.integrations.embeddings import embed_texts
from app.integrations.indian_kanoon import (
    IndianKanoonProviderError,
    KanoonResult,
    get_indian_kanoon_provider,
)
from app.integrations.llm import complete

logger = get_logger(__name__)
settings = get_settings()

_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)

_DISTRICT_COURT_TERMS = ["district court", "sessions court", "magistrate", "civil judge"]

INSUFFICIENT_MESSAGE = (
    "No reliable authority could be found to confidently answer this query. "
    "Please consult a full-text legal database or a colleague for verification."
)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _parse_json_response(raw: str) -> dict:
    cleaned = _JSON_FENCE_RE.sub("", raw).strip()
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    logger.warning("research_generate_parse_failed", raw_preview=raw[:200])
    return {}


def _looks_like_valid_url(url: str) -> bool:
    return bool(url) and (url.startswith("http://") or url.startswith("https://"))


async def _verify_url_resolves(url: str) -> bool:
    """
    Real-mode citation verification per contract: "the source_url
    resolves". In FAKE_MODE (no real provider/network), we can't
    meaningfully HEAD-check a fixture URL, so we fall back to a
    well-formedness check -- the real HTTP check activates the moment
    a real provider is configured.
    """
    if settings.fake_mode:
        return _looks_like_valid_url(url)

    if not _looks_like_valid_url(url):
        return False

    import httpx

    try:
        async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
            response = await client.head(url)
            return response.status_code < 400
    except httpx.HTTPError:
        return False


async def _retrieve_and_rerank(english_query: str) -> list[KanoonResult]:
    provider = get_indian_kanoon_provider()

    try:
        candidates = await provider.search(english_query, top_k=settings.research_retrieve_top_k)
    except IndianKanoonProviderError:
        logger.warning("indian_kanoon_search_failed", query=english_query)
        return []

    if not candidates:
        return []

    if settings.fake_mode or settings.embedding_provider == "fake":
        # Fake-mode embeddings are deterministic hash noise with no
        # semantic signal -- re-ranking with them would only scramble
        # the keyword-relevance ordering the (also fake-mode)
        # FixtureProvider.search() already produced. Trust that
        # ordering instead; real embeddings re-rank for real.
        return candidates[: settings.research_rerank_top_k]

    texts = [english_query] + [c.snippet for c in candidates]
    vectors = await embed_texts(texts)
    query_vector, candidate_vectors = vectors[0], vectors[1:]

    scored = list(zip(candidate_vectors, candidates, strict=True))
    scored.sort(key=lambda pair: _cosine_similarity(query_vector, pair[0]), reverse=True)

    return [result for _vec, result in scored[: settings.research_rerank_top_k]]


async def _generate_answer(query: str, fragments: list[KanoonResult], language: str) -> dict:
    fragment_payload = [
        {
            "index": i + 1,
            "case_title": f.case_title,
            "court": f.court,
            "year": f.year,
            "snippet": f.snippet,
        }
        for i, f in enumerate(fragments)
    ]

    system, user = build_research_generation_prompt(query, fragment_payload, language=language)
    raw = await complete(system=system, user=user)
    return _parse_json_response(raw)


async def _verify_citations(
    llm_citations: list[dict], fragments: list[KanoonResult]
) -> list[dict]:
    """
    Contract B.7 "non-negotiable": for each citation, confirm the
    document ID exists via the provider AND the source_url resolves.
    Drop any that fail either check. Citation metadata (title/court/
    year/url) always comes from our own retrieval data (`fragments`),
    never from the LLM's output -- the LLM only selects which
    fragments it used and why.
    """
    provider = get_indian_kanoon_provider()
    verified: list[dict] = []

    for citation in llm_citations:
        idx = citation.get("fragment_index")
        if not isinstance(idx, int) or not (1 <= idx <= len(fragments)):
            continue

        fragment = fragments[idx - 1]

        try:
            fetched = await provider.fetch_document(fragment.doc_id)
        except IndianKanoonProviderError:
            fetched = None

        if fetched is None:
            logger.warning("citation_verification_failed_doc_not_found", doc_id=fragment.doc_id)
            continue

        if not await _verify_url_resolves(fragment.source_url):
            logger.warning("citation_verification_failed_url", doc_id=fragment.doc_id)
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
    if verified_count < settings.research_min_verified_citations:
        return "insufficient"
    if verified_count >= 4:
        return "high"
    return "medium"


async def research(*, query: str, language: str = "en") -> dict:
    """
    Returns the AIJob.result shape for type="research" (contract B.7):
    answer_markdown, citations[], confidence.
    """
    normalized = await normalize_query(query)
    english_query = normalized["english_query"]

    fragments = await _retrieve_and_rerank(english_query)

    if not fragments:
        return {
            "answer_markdown": INSUFFICIENT_MESSAGE,
            "citations": [],
            "confidence": "insufficient",
        }

    generated = await _generate_answer(query, fragments, language)
    llm_citations = generated.get("citations") or []

    verified_citations = await _verify_citations(llm_citations, fragments)
    confidence = _confidence_for(len(verified_citations))

    answer_markdown = generated.get("answer_markdown") or ""

    if confidence == "insufficient":
        answer_markdown = INSUFFICIENT_MESSAGE
        verified_citations = []
    else:
        lowered = query.lower()
        if any(term in lowered for term in _DISTRICT_COURT_TERMS):
            answer_markdown += (
                "\n\n*Note: case-law coverage is sparser for district and "
                "subordinate courts than for High Courts and the Supreme "
                "Court; please verify against a full-text database for "
                "district-level matters.*"
            )

    return {
        "answer_markdown": answer_markdown,
        "citations": verified_citations,
        "confidence": confidence,
    }
