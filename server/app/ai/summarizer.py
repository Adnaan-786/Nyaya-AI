"""C.9 document summarizer: classify, then extract, with map-reduce for long documents.

Two passes rather than one, because the useful summary of a chargesheet and the useful
summary of a rent agreement are not the same summary — the type is detected first so
the extraction prompt can ask for the fields that type actually has (see `_TYPE_FOCUS`
in `app/ai/prompts.py`). The classification call is capped at 16 tokens, so the second
pass costs almost nothing.

Returns the plain `summarize` result dict from B.7; callers that put it in front of the
app validate it against `SummarizeResult` first, which is where the contract is
enforced.
"""

import logging

from app.ai.parsing import parse_json_object
from app.ai.prompts import (
    build_classification_prompt,
    build_extraction_prompt,
    build_reduce_prompt,
)
from app.integrations.llm import complete

logger = logging.getLogger(__name__)

_KNOWN_DOC_TYPES = {"chargesheet", "judgment", "notice", "agreement", "other"}

# Above this many words, run map-reduce over chunks instead of one extraction pass
# (C.9: "long docs: map-reduce over chunks"). Below it, chunking only costs extra
# calls and loses the cross-chunk context a single pass has for free.
LONG_DOCUMENT_WORD_THRESHOLD = 1200

EMPTY_SUMMARY = {
    "summary_markdown": "No text could be extracted from this document.",
    "key_points": [],
    "parties": [],
    "sections_invoked": [],
    "dates": [],
    "doc_type_detected": "other",
}


async def detect_doc_type(text_excerpt: str) -> str:
    system, user = build_classification_prompt(text_excerpt)
    raw = await complete(system=system, user=user, max_tokens=16)

    normalized = raw.strip().lower().strip(".")
    return normalized if normalized in _KNOWN_DOC_TYPES else "other"


async def _extract_single_pass(doc_type: str, text: str, language: str) -> dict:
    system, user = build_extraction_prompt(doc_type, text, language=language)
    raw = await complete(system=system, user=user, json_mode=True)
    parsed = parse_json_object(raw, task="extract_summary")

    return {
        "summary_markdown": parsed.get("summary_markdown") or "",
        "key_points": parsed.get("key_points") or [],
        "parties": parsed.get("parties") or [],
        "sections_invoked": parsed.get("sections_invoked") or [],
        "dates": parsed.get("dates") or [],
        "doc_type_detected": doc_type,
    }


async def _reduce(partial_results: list[dict], language: str) -> dict:
    """Prose is re-summarised by the model; the list fields are unioned in code.

    Asking the model to merge the section and date lists would give it a second
    opportunity to drop or embellish a statutory reference it already extracted
    correctly. Set union over its own map-step output cannot invent one.
    """
    partial_summaries = [r["summary_markdown"] for r in partial_results if r["summary_markdown"]]

    system, user = build_reduce_prompt(partial_summaries, language=language)
    raw = await complete(system=system, user=user, json_mode=True)
    reduced = parse_json_object(raw, task="extract_summary_reduce")

    def _union(field: str, cap: int) -> list[str]:
        seen: list[str] = []
        for result in partial_results:
            for item in result.get(field, []):
                if item not in seen:
                    seen.append(item)
        return seen[:cap]

    return {
        "summary_markdown": reduced.get("summary_markdown") or " ".join(partial_summaries)[:2000],
        "key_points": reduced.get("key_points") or _union("key_points", 8),
        "parties": _union("parties", 10),
        "sections_invoked": _union("sections_invoked", 20),
        "dates": _union("dates", 20),
        "doc_type_detected": (
            partial_results[0]["doc_type_detected"] if partial_results else "other"
        ),
    }


async def summarize_document(
    *, text: str, chunks: list[str] | None = None, language: str = "en"
) -> dict:
    """The B.7 `summarize` result shape: summary_markdown, key_points, parties,
    sections_invoked, dates, doc_type_detected."""
    if not text or not text.strip():
        return dict(EMPTY_SUMMARY)

    doc_type = await detect_doc_type(text[:3000])

    word_count = len(text.split())
    use_map_reduce = bool(chunks) and len(chunks) > 1 and word_count > LONG_DOCUMENT_WORD_THRESHOLD

    if not use_map_reduce:
        return await _extract_single_pass(doc_type, text, language)

    partial_results = [
        await _extract_single_pass(doc_type, chunk, language) for chunk in chunks or []
    ]
    return await _reduce(partial_results, language)
