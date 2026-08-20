import json
import re

from app.ai.prompts import (
    build_classification_prompt,
    build_extraction_prompt,
    build_reduce_prompt,
)
from app.core.logging import get_logger
from app.integrations.llm import complete

logger = get_logger(__name__)

_KNOWN_DOC_TYPES = {"chargesheet", "judgment", "notice", "agreement", "other"}
_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)

# Above this many words, run map-reduce over chunks instead of a
# single extraction pass (plan C.9: "Long docs: map-reduce over chunks").
LONG_DOCUMENT_WORD_THRESHOLD = 1200


def _parse_json_response(raw: str) -> dict:
    cleaned = _JSON_FENCE_RE.sub("", raw).strip()
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    logger.warning("summarizer_json_parse_failed", raw_preview=raw[:200])
    return {}


async def detect_doc_type(text_excerpt: str) -> str:
    system, user = build_classification_prompt(text_excerpt)
    raw = await complete(system=system, user=user, max_tokens=16)

    normalized = raw.strip().lower().strip(".")
    return normalized if normalized in _KNOWN_DOC_TYPES else "other"


async def _extract_single_pass(doc_type: str, text: str, language: str) -> dict:
    system, user = build_extraction_prompt(doc_type, text, language=language)
    raw = await complete(system=system, user=user)
    parsed = _parse_json_response(raw)

    return {
        "summary_markdown": parsed.get("summary_markdown") or "",
        "key_points": parsed.get("key_points") or [],
        "parties": parsed.get("parties") or [],
        "sections_invoked": parsed.get("sections_invoked") or [],
        "dates": parsed.get("dates") or [],
        "doc_type_detected": doc_type,
    }


async def _reduce(partial_results: list[dict], language: str) -> dict:
    partial_summaries = [r["summary_markdown"] for r in partial_results if r["summary_markdown"]]

    system, user = build_reduce_prompt(partial_summaries, language=language)
    raw = await complete(system=system, user=user)
    reduced = _parse_json_response(raw)

    def _union(field: str, cap: int) -> list[str]:
        seen: list[str] = []
        for r in partial_results:
            for item in r.get(field, []):
                if item not in seen:
                    seen.append(item)
        return seen[:cap]

    return {
        "summary_markdown": reduced.get("summary_markdown") or " ".join(partial_summaries)[:2000],
        "key_points": reduced.get("key_points") or _union("key_points", 8),
        "parties": _union("parties", 10),
        "sections_invoked": _union("sections_invoked", 20),
        "dates": _union("dates", 20),
        "doc_type_detected": partial_results[0]["doc_type_detected"] if partial_results else "other",
    }


async def summarize_document(
    *, text: str, chunks: list[str] | None = None, language: str = "en"
) -> dict:
    """
    Returns the AIJob.result shape for type="summarize" (contract B.7):
    summary_markdown, key_points[], parties[], sections_invoked[],
    dates[], doc_type_detected.
    """
    if not text or not text.strip():
        return {
            "summary_markdown": "No text could be extracted from this document.",
            "key_points": [],
            "parties": [],
            "sections_invoked": [],
            "dates": [],
            "doc_type_detected": "other",
        }

    doc_type = await detect_doc_type(text[:3000])

    word_count = len(text.split())
    use_map_reduce = bool(chunks) and len(chunks) > 1 and word_count > LONG_DOCUMENT_WORD_THRESHOLD

    if not use_map_reduce:
        return await _extract_single_pass(doc_type, text, language)

    partial_results = []
    for chunk in chunks:
        partial_results.append(await _extract_single_pass(doc_type, chunk, language))

    return await _reduce(partial_results, language)
