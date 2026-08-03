"""Groq client for the AI services (C.1 "the differentiator").

Groq (groq.com) hosts open models (Llama 3.3, etc.) behind a fast inference API —
not to be confused with Grok, x.ai's unrelated model of a near-identical name; a
`gsk_`-prefixed key is Groq's.

Groq's API is OpenAI-compatible chat completions, reached over plain HTTP with
`httpx` — the same way every other outbound integration in this server talks to a
third party (see `ecourts.py`), rather than adding a second HTTP-client dependency
for one integration.

Two things are non-negotiable in a legal product, and neither is provider-specific:

1. **Structured output, not prose parsing.** The model is asked for JSON mode and
   given the exact schema in the system prompt; the response is validated against
   the Pydantic result model before anything downstream sees it, so a malformed
   reply is a caught, reported failure — never a half-parsed screen with blank
   fields.
2. **A response that doesn't validate is a refusal, not a crash.** If the model
   declines, wanders off-schema, or the API call itself fails, that surfaces as a
   failed job with a message — nothing here should ever take the background worker
   down with it (the worker's own broad `except Exception` in `app/api/ai.py` is the
   second line of defence, but this module still validates explicitly rather than
   leaning on that alone).

FAKE_MODE returns realistic canned results so the whole AI surface is demonstrable
without an API key or spend.
"""

import json
import logging

import httpx
from pydantic import ValidationError

from app.core.config import get_settings
from app.schemas.ai import Citation, ResearchResult, SummarizeResult

logger = logging.getLogger(__name__)
settings = get_settings()

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

# Generous relative to the 30s estimate B.7 gives the app — a slow completion should
# time out and fail the job cleanly rather than hang the worker indefinitely.
REQUEST_TIMEOUT_SECONDS = 90
MAX_TOKENS = 16000

SUMMARIZE_SYSTEM = """You are assisting an Indian advocate by summarising a legal document.

Write for a lawyer who will act on this, not for a layperson. Be precise about
statutory sections, parties, and dates — those are what they will check first.

Use the document's own terms; do not translate Indian legal vocabulary into
foreign equivalents (a "chargesheet" is not an "indictment", an "FIR" is not a
"police report"). If the document is unclear or truncated, say so in the summary
rather than filling the gap with a plausible guess.

Only state what the document says. Never infer facts that are not in it.

Respond with a single JSON object and nothing else — no prose before or after it,
no markdown code fence around it. The object must have exactly these keys:
- "summary_markdown": string, a 2-5 paragraph summary in Markdown.
- "key_points": array of strings, bulleted findings, most important first.
- "parties": array of strings, named parties (petitioners, respondents, accused).
- "sections_invoked": array of strings, statutory sections cited, e.g.
  "Section 138 NI Act", "IPC 420".
- "dates": array of strings, significant dates as they appear in the document.
- "doc_type_detected": string, e.g. chargesheet, order, agreement, notice, affidavit,
  judgment."""

RESEARCH_SYSTEM = """You are assisting an Indian advocate with case-law research.

Ground every claim in Indian law — the Supreme Court of India, High Courts, and
Indian statutes. Foreign authority is not useful here unless the user asks for it.

The user may write in Hinglish (Hindi and English mixed, Latin script). Understand
it naturally and answer in the language they used.

On confidence, be strict, because the cost of the two errors is not symmetric:
- "high": directly on point, from authority you are confident exists.
- "medium": analogous or persuasive rather than binding.
- "insufficient": you cannot recall reliable authority. Say so plainly in
  answer_markdown and return an empty citations list.

Never invent a case name, citation, court, year, or URL. A fabricated authority
that a lawyer carries into court is far worse than admitting you do not know.

Respond with a single JSON object and nothing else — no prose before or after it,
no markdown code fence around it. The object must have exactly these keys:
- "answer_markdown": string.
- "citations": array of objects, each with "case_title", "court", "year",
  "source_url", and "relevance_note" (one sentence on why this authority applies).
  Empty array when confidence is "insufficient".
- "confidence": one of "high", "medium", "insufficient"."""


def _is_live() -> bool:
    return not settings.fake_mode and bool(settings.groq_api_key)


async def _complete(system: str, user_content: str) -> dict:
    """One JSON-mode chat completion, parsed but not yet validated against either
    result schema — that happens at each call site, where the expected shape is
    known."""
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        response = await client.post(
            GROQ_API_URL,
            headers={"Authorization": f"Bearer {settings.groq_api_key}"},
            json={
                "model": settings.groq_model,
                "max_tokens": MAX_TOKENS,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_content},
                ],
            },
        )
        if response.is_error:
            # httpx's own exception message drops the response body, which is
            # exactly where xAI explains *why* — an invalid model name, a rejected
            # parameter, an auth failure. Logging it here is the difference between
            # a one-line guess and actually knowing what to fix.
            logger.error("xAI returned %s: %s", response.status_code, response.text)
        response.raise_for_status()
        body = response.json()

    choice = (body.get("choices") or [None])[0]
    if choice is None:
        raise LlmRefusal("The assistant returned no response.")

    # xAI surfaces a moderation/length cutoff the same way OpenAI-compatible APIs
    # do — a finish_reason other than "stop" means the content is not a complete,
    # trustworthy answer even if something came back.
    finish_reason = choice.get("finish_reason")
    content = (choice.get("message") or {}).get("content")
    if finish_reason not in ("stop", None) or not content:
        raise LlmRefusal("The assistant could not complete this request.")

    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        raise LlmRefusal("The assistant's response was not valid JSON.") from exc


async def summarize_document(text: str, doc_type_hint: str | None) -> SummarizeResult:
    if not _is_live():
        return _fake_summary(text, doc_type_hint)

    hint = f"\n\nThe user believes this is a {doc_type_hint}." if doc_type_hint else ""
    try:
        parsed = await _complete(
            SUMMARIZE_SYSTEM,
            f"Summarise this document.{hint}\n\n<document>\n{text}\n</document>",
        )
        return SummarizeResult.model_validate(parsed)
    except httpx.HTTPStatusError:
        logger.exception("summarize failed")
        raise
    except ValidationError as exc:
        raise LlmRefusal("The assistant's response did not match the expected shape.") from exc


async def research_case_law(query: str, language: str) -> ResearchResult:
    if not _is_live():
        return _fake_research(query, language)

    try:
        parsed = await _complete(RESEARCH_SYSTEM, query)
        return ResearchResult.model_validate(parsed)
    except httpx.HTTPStatusError:
        logger.exception("research failed")
        raise
    except ValidationError as exc:
        raise LlmRefusal("The assistant's response did not match the expected shape.") from exc


class LlmRefusal(Exception):
    """The model declined, or its reply didn't hold up. Surfaced to the app as a
    failed job, not a 500."""


# --- Fake mode ------------------------------------------------------------------


def _fake_summary(text: str, doc_type_hint: str | None) -> SummarizeResult:
    """Derived from the real extracted text, so the demo reflects the actual upload
    rather than a fixed blob that contradicts what is on screen."""
    snippet = " ".join(text.split())[:400]
    sections = [s for s in ("Section 138", "Section 420", "Section 498A") if s in text]
    return SummarizeResult(
        summary_markdown=(
            "**[Demo summary]** This document was processed with the AI provider "
            "disabled, so the text below is extracted rather than analysed.\n\n"
            f"{snippet}…"
        ),
        key_points=[
            "Configure GROQ_API_KEY and set FAKE_MODE=false for real analysis.",
            "Extraction and search are fully functional in this mode.",
        ],
        parties=[],
        sections_invoked=sections,
        dates=[],
        doc_type_detected=doc_type_hint or "unknown",
    )


def _fake_research(query: str, language: str) -> ResearchResult:
    """Deliberately returns `insufficient` with no citations.

    Returning a plausible-looking fake citation would be the single most dangerous
    thing this demo could do — someone would eventually carry it into court.
    """
    note = (
        "AI provider is not configured on this server, so no authority was searched."
        if language == "en"
        else "Is server par AI provider configure nahin hai, isliye koi authority nahin dekhi gayi."
    )
    return ResearchResult(
        answer_markdown=f"**[Demo mode]** {note}\n\n> Your question: {query}",
        citations=[],
        confidence="insufficient",
    )


__all__ = [
    "Citation",
    "LlmRefusal",
    "research_case_law",
    "summarize_document",
]
