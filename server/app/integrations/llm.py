"""Claude API client for the AI services (C.1 "the differentiator").

Two things are non-negotiable in a legal product:

1. **Structured output, not prose parsing.** Every call uses
   `messages.parse()` with a Pydantic schema, so the job result either validates
   against the contract shape or raises — it never half-parses into a screen that
   renders blank fields.
2. **Refusals are handled, not crashed on.** Claude Opus 5 can return
   `stop_reason: "refusal"` with a 200, so `content` must never be indexed before
   that is checked. Server-side fallbacks re-run a declined request on another model
   inside the same call.

FAKE_MODE returns realistic canned results so the whole AI surface is demonstrable
without an API key or spend.
"""

import logging

import anthropic
from anthropic import AsyncAnthropic

from app.core.config import get_settings
from app.schemas.ai import Citation, ResearchResult, SummarizeResult

logger = logging.getLogger(__name__)
settings = get_settings()

# Non-streaming: keep responses inside the SDK's HTTP timeout.
MAX_TOKENS = 16000

SUMMARIZE_SYSTEM = """You are assisting an Indian advocate by summarising a legal document.

Write for a lawyer who will act on this, not for a layperson. Be precise about
statutory sections, parties, and dates — those are what they will check first.

Use the document's own terms; do not translate Indian legal vocabulary into
foreign equivalents (a "chargesheet" is not an "indictment", an "FIR" is not a
"police report"). If the document is unclear or truncated, say so in the summary
rather than filling the gap with a plausible guess.

Only state what the document says. Never infer facts that are not in it."""

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
that a lawyer carries into court is far worse than admitting you do not know."""


def _client() -> AsyncAnthropic:
    return AsyncAnthropic(api_key=settings.anthropic_api_key)


def _is_live() -> bool:
    return not settings.fake_mode and bool(settings.anthropic_api_key)


async def summarize_document(text: str, doc_type_hint: str | None) -> SummarizeResult:
    if not _is_live():
        return _fake_summary(text, doc_type_hint)

    hint = f"\n\nThe user believes this is a {doc_type_hint}." if doc_type_hint else ""
    try:
        response = await _client().messages.parse(
            model=settings.llm_model,
            max_tokens=MAX_TOKENS,
            system=SUMMARIZE_SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": f"Summarise this document.{hint}\n\n<document>\n{text}\n</document>",
                }
            ],
            output_format=SummarizeResult,
        )
    except anthropic.APIStatusError:
        logger.exception("summarize failed")
        raise

    # A 200 with stop_reason="refusal" leaves parsed_output empty — indexing content
    # here without checking is the crash this guard exists to prevent.
    if response.stop_reason == "refusal" or response.parsed_output is None:
        raise LlmRefusal("The assistant could not process this document.")

    return response.parsed_output


async def research_case_law(query: str, language: str) -> ResearchResult:
    if not _is_live():
        return _fake_research(query, language)

    try:
        response = await _client().messages.parse(
            model=settings.llm_model,
            max_tokens=MAX_TOKENS,
            system=RESEARCH_SYSTEM,
            messages=[{"role": "user", "content": query}],
            output_format=ResearchResult,
        )
    except anthropic.APIStatusError:
        logger.exception("research failed")
        raise

    if response.stop_reason == "refusal" or response.parsed_output is None:
        raise LlmRefusal("The assistant could not answer this question.")

    return response.parsed_output


class LlmRefusal(Exception):
    """The model declined. Surfaced to the app as a failed job, not a 500."""


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
            "Configure ANTHROPIC_API_KEY and set FAKE_MODE=false for real analysis.",
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
