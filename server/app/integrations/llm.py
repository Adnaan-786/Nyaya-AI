"""LLM completions for the AI services (C.1 "the differentiator").

One provider switch — `fake | groq | anthropic` — selected by `LLM_PROVIDER`, with
every provider reached over plain `httpx`, the same way every other outbound
integration in this server talks to a third party (see `ecourts.py`), rather than
adding a vendor SDK per backend.

`groq` is what the deployed instance runs and therefore the default. Groq (groq.com)
hosts open models (Llama 3.3, etc.) behind an OpenAI-compatible chat-completions API
— not to be confused with Grok, x.ai's unrelated model of a near-identical name; a
`gsk_`-prefixed key is Groq's.

Two things are non-negotiable in a legal product, and neither is provider-specific:

1. **Structured output, not prose parsing.** The model is asked for JSON and given the
   exact schema in the system prompt; the response is validated against the Pydantic
   result model before anything downstream sees it, so a malformed reply is a caught,
   reported failure — never a half-parsed screen with blank fields.
2. **A response that doesn't validate is a refusal, not a crash.** If the model
   declines, wanders off-schema, or the API call itself fails, that surfaces as a
   failed job with a message — nothing here should ever take the background worker
   down with it (the worker's own broad `except Exception` in `app/api/ai.py` is the
   second line of defence, but this module still validates explicitly rather than
   leaning on that alone).

`fake` is not merely a test seam. FAKE_MODE — or any provider whose key is missing —
returns realistic results derived from the real input, so the whole AI surface is
demonstrable without a key or spend, and a provider that has not been provisioned
degrades to a demo rather than a 500.
"""

import json
import logging

import httpx
from pydantic import ValidationError

from app.ai.fake_llm import fake_complete
from app.core.config import get_settings
from app.schemas.ai import Citation, ResearchResult, SummarizeResult

logger = logging.getLogger(__name__)
settings = get_settings()

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"

# Generous relative to the 30s estimate B.7 gives the app — a slow completion should
# time out and fail the job cleanly rather than hang the worker indefinitely.
REQUEST_TIMEOUT_SECONDS = 90

# Groq's free/on-demand tier caps llama-3.3-70b-versatile at 12,000 tokens per
# minute *total* (prompt + completion) — a holdover value from Claude's much higher
# ceiling (16000, output alone) blew straight through that on the very first live
# call. A research/summary answer plus citations comfortably fits in a few thousand
# tokens, so this stays well under the cap with room for the prompt on top. Anthropic
# has no such ceiling and uses `llm_max_tokens` instead.
GROQ_MAX_TOKENS = 4000

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
- "high": directly on point, from authority you are confident exists AND for which
  you can give a real, correct source_url.
- "medium": analogous or persuasive rather than binding, same source_url requirement.
- "insufficient": you cannot recall reliable authority, or you can recall a case but
  are not certain enough of its citation to give a real URL for it. Say so plainly
  in answer_markdown and return an empty citations list.

Never invent a case name, citation, court, year, or URL. A fabricated authority
that a lawyer carries into court is far worse than admitting you do not know. This
is not a soft preference — it is the single most dangerous mistake you can make
in this role. Concretely:
- Every citation's source_url MUST be a real, specific URL you are confident
  resolves to that actual judgment (e.g. an indiankanoon.org/doc/ link, or the
  court's own site). An empty string, a placeholder, a guessed URL pattern, or a
  search-results link is not acceptable — if you cannot give one, drop that
  citation entirely rather than include it with a blank or invented URL.
- If dropping unverifiable citations leaves you with none, the confidence for
  this answer is "insufficient", even if you are otherwise sure of the legal
  proposition itself. A correct rule of law with a fabricated case behind it is
  still a fabrication problem, not a citation-formatting one.
- Prefer well-known, landmark judgments you have genuinely seen cited many times
  over obscure-sounding cases your training data is thin on — thin recall is
  exactly where fabrication happens.

Respond with a single JSON object and nothing else — no prose before or after it,
no markdown code fence around it. The object must have exactly these keys:
- "answer_markdown": string.
- "citations": array of objects, each with "case_title", "court", "year",
  "source_url", and "relevance_note" (one sentence on why this authority applies).
  Empty array when confidence is "insufficient".
- "confidence": one of "high", "medium", "insufficient"."""


class LlmRefusal(Exception):
    """The model declined, or its reply didn't hold up. Surfaced to the app as a
    failed job, not a 500."""


class LlmProviderError(Exception):
    """The provider itself failed — misconfigured, unreachable, or an error status.

    Distinct from `LlmRefusal`: nothing about the request was wrong, so the app is
    told the service is temporarily unavailable rather than shown a message about
    its own document or query.
    """


def _active_provider() -> str:
    """The provider that will actually answer, which is not always the configured one.

    FAKE_MODE outranks everything, and a provider with no key falls back to `fake`
    rather than erroring: the demo has shipped ahead of its API keys more than once,
    and a screen full of clearly-marked demo output is a far better failure than a
    red toast on every AI action.
    """
    if settings.fake_mode:
        return "fake"

    provider = settings.llm_provider
    if provider == "groq" and not settings.groq_api_key:
        return "fake"
    if provider == "anthropic" and not settings.anthropic_api_key:
        return "fake"
    return provider


def _is_live() -> bool:
    return _active_provider() != "fake"


async def complete(
    *, system: str, user: str, max_tokens: int | None = None, json_mode: bool = False
) -> str:
    """The model's raw text completion for a single-turn prompt.

    Callers that need structured output parse the returned string themselves — that
    is what the real Messages/chat-completions APIs give back too, and pretending
    otherwise here would just move the malformed-JSON problem somewhere less visible.
    `json_mode` is a hint the provider may or may not enforce natively; the prompt
    still has to ask for JSON.
    """
    provider = _active_provider()

    if provider == "fake":
        return fake_complete(system=system, user=user)
    if provider == "groq":
        return await _complete_groq(
            system=system, user=user, max_tokens=max_tokens, json_mode=json_mode
        )
    if provider == "anthropic":
        return await _complete_anthropic(system=system, user=user, max_tokens=max_tokens)

    raise LlmProviderError(f"Unknown LLM provider: {provider!r}")


async def _complete_groq(
    *, system: str, user: str, max_tokens: int | None, json_mode: bool
) -> str:
    payload: dict = {
        "model": settings.groq_model,
        "max_tokens": max_tokens or GROQ_MAX_TOKENS,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        response = await client.post(
            GROQ_API_URL,
            headers={"Authorization": f"Bearer {settings.groq_api_key}"},
            json=payload,
        )
        if response.is_error:
            # httpx's own exception message drops the response body, which is
            # exactly where Groq explains *why* — an invalid model name, a rejected
            # parameter, an auth failure. Logging it here is the difference between
            # a one-line guess and actually knowing what to fix.
            logger.error("groq returned %s: %s", response.status_code, response.text)
        response.raise_for_status()
        body = response.json()

    choice = (body.get("choices") or [None])[0]
    if choice is None:
        raise LlmRefusal("The assistant returned no response.")

    # OpenAI-compatible APIs surface a moderation or length cutoff this way: a
    # finish_reason other than "stop" means the content is not a complete,
    # trustworthy answer even if something came back.
    finish_reason = choice.get("finish_reason")
    content = (choice.get("message") or {}).get("content")
    if finish_reason not in ("stop", None) or not content:
        raise LlmRefusal("The assistant could not complete this request.")

    return content


async def _complete_anthropic(*, system: str, user: str, max_tokens: int | None) -> str:
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        response = await client.post(
            ANTHROPIC_API_URL,
            headers={
                "x-api-key": settings.anthropic_api_key or "",
                "anthropic-version": ANTHROPIC_VERSION,
                "content-type": "application/json",
            },
            json={
                "model": settings.llm_model,
                "max_tokens": max_tokens or settings.llm_max_tokens,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            },
        )

    if response.is_error:
        logger.error("anthropic returned %s: %s", response.status_code, response.text)
        raise LlmProviderError(f"Anthropic API error {response.status_code}")

    body = response.json()
    if body.get("stop_reason") == "refusal":
        raise LlmRefusal("The assistant declined this request.")

    text = "\n".join(b["text"] for b in body.get("content", []) if b.get("type") == "text")
    if not text:
        raise LlmRefusal("The assistant returned no response.")
    return text


def _strip_code_fence(raw: str) -> str:
    """Both prompts forbid a code fence, but only Groq's JSON mode makes that a
    guarantee — Anthropic has no equivalent switch, so a ```json wrapper is a live
    possibility there and is not worth failing an entire job over."""
    text = raw.strip()
    if not text.startswith("```"):
        return text
    body = text.split("\n", 1)[1] if "\n" in text else ""
    return body.rsplit("```", 1)[0].strip()


async def _complete_json(system: str, user: str) -> dict:
    """One JSON completion, parsed but not yet validated against either result
    schema — that happens at each call site, where the expected shape is known."""
    raw = await complete(system=system, user=user, json_mode=True)
    try:
        return json.loads(_strip_code_fence(raw))
    except json.JSONDecodeError as exc:
        raise LlmRefusal("The assistant's response was not valid JSON.") from exc


async def summarize_document(text: str, doc_type_hint: str | None) -> SummarizeResult:
    if not _is_live():
        return _fake_summary(text, doc_type_hint)

    hint = f"\n\nThe user believes this is a {doc_type_hint}." if doc_type_hint else ""
    try:
        parsed = await _complete_json(
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
        parsed = await _complete_json(RESEARCH_SYSTEM, query)
        result = ResearchResult.model_validate(parsed)
    except httpx.HTTPStatusError:
        logger.exception("research failed")
        raise
    except ValidationError as exc:
        raise LlmRefusal("The assistant's response did not match the expected shape.") from exc

    return _drop_unverifiable_citations(result)


def _drop_unverifiable_citations(result: ResearchResult) -> ResearchResult:
    """The system prompt tells the model to omit a citation it can't back with a
    real URL, but a prompt is a request, not a guarantee — this is the actual
    guarantee. A citation without something that at least looks like a real URL is
    treated exactly as if the model had reported no reliable authority at all,
    because that's what it functionally is: unverifiable, and unverifiable is not
    a state this feature is allowed to present as "high" or "medium" confidence.
    """
    verifiable = [c for c in result.citations if c.source_url.strip().lower().startswith("http")]

    if len(verifiable) == len(result.citations):
        return result

    logger.warning(
        "dropped %d unverifiable citation(s) from a research answer",
        len(result.citations) - len(verifiable),
    )
    return result.model_copy(
        update={
            "citations": verifiable,
            "confidence": "insufficient" if not verifiable else result.confidence,
        }
    )


# --- Fake mode ------------------------------------------------------------------
#
# These two endpoints predate the provider switch and keep their own fakes rather
# than routing through `app/ai/fake_llm.py`: what they need is not a schema-correct
# blob but a *self-explaining* one. The summary says why it is not an analysis, and
# the research answer refuses outright — see `_fake_research`.


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
    "LlmProviderError",
    "LlmRefusal",
    "complete",
    "research_case_law",
    "summarize_document",
]
