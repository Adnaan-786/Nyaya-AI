"""Query normalisation: the step that makes a Hinglish question searchable."""

import pytest

from app.ai.query_normalizer import normalize_query

pytestmark = pytest.mark.asyncio


async def test_statutory_sections_are_pulled_out() -> None:
    result = await normalize_query("What is the bail process under Section 439 CrPC?")

    assert any("439" in section for section in result["sections"])


async def test_years_are_pulled_out() -> None:
    result = await normalize_query("Any updates on cases decided in 2021 or 2022?")

    assert 2021 in result["years"]
    assert 2022 in result["years"]


async def test_a_named_court_is_pulled_out() -> None:
    result = await normalize_query("What did the Bombay High Court hold on this?")

    assert any("high court" in court.lower() for court in result["courts"])


async def test_a_query_with_no_signals_still_yields_a_searchable_query() -> None:
    result = await normalize_query("simple query with no signals")

    assert result["english_query"]


async def test_an_unusable_response_falls_back_to_the_original_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A normalisation hiccup must degrade retrieval, never block it."""

    async def _garbage(*, system: str, user: str, **kwargs) -> str:
        return "sorry, I cannot do that"

    monkeypatch.setattr("app.ai.query_normalizer.complete", _garbage)

    result = await normalize_query("Section 138 mein interim compensation kab milta hai?")

    assert result["english_query"] == "Section 138 mein interim compensation kab milta hai?"
    assert result["sections"] == []


async def test_every_key_retrieval_expects_is_always_present() -> None:
    result = await normalize_query("test query")

    assert set(result) == {"english_query", "sections", "acts", "years", "courts"}
