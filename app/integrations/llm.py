"""
LLM completion provider for AI Services (module M7).

Same policy as every other external integration in this codebase
(MSG91, eCourts, Document AI, embeddings): FAKE_MODE gives a fully
functional, deterministic, offline codepath so the whole pipeline is
exercisable without an API key; the real call is a clearly-marked stub
until ANTHROPIC_API_KEY is provisioned (plan C.1: "LLM provider with
zero-data-retention agreement").
"""

from app.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class LLMProviderError(Exception):
    """Raised when the LLM provider fails to produce a completion."""


async def complete(*, system: str, user: str, max_tokens: int | None = None) -> str:
    """
    Returns the model's raw text completion for a single-turn prompt.

    Callers that need structured output (JSON) are responsible for
    parsing the returned string themselves and handling malformed
    output -- this function's contract is "best-effort text back",
    matching how the real Anthropic Messages API behaves too.
    """
    if settings.fake_mode or settings.llm_provider == "fake":
        logger.info("llm_fake_completion", system_len=len(system), user_len=len(user))
        from app.ai.fake_llm import fake_complete

        return fake_complete(system=system, user=user)

    if settings.llm_provider == "anthropic":
        return await _complete_anthropic(system=system, user=user, max_tokens=max_tokens)

    raise LLMProviderError(f"Unknown LLM provider: {settings.llm_provider!r}")


async def _complete_anthropic(
    *, system: str, user: str, max_tokens: int | None
) -> str:
    if not settings.anthropic_api_key:
        raise NotImplementedError(
            "Real Anthropic completion is not configured. Set "
            "ANTHROPIC_API_KEY and LLM_PROVIDER=anthropic, or leave "
            "LLM_PROVIDER=fake (or FAKE_MODE=true) for now."
        )

    import httpx

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": settings.anthropic_api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": settings.llm_model,
                "max_tokens": max_tokens or settings.llm_max_tokens,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            },
        )

    if response.status_code >= 400:
        raise LLMProviderError(
            f"Anthropic API error {response.status_code}: {response.text[:500]}"
        )

    data = response.json()
    text_blocks = [b["text"] for b in data.get("content", []) if b.get("type") == "text"]
    return "\n".join(text_blocks)
