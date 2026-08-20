import pytest

from app.ai.query_normalizer import normalize_query


@pytest.mark.asyncio
async def test_normalize_query_extracts_sections():
    result = await normalize_query("What is the bail process under Section 439 CrPC?")
    assert any("439" in s for s in result["sections"])


@pytest.mark.asyncio
async def test_normalize_query_extracts_years():
    result = await normalize_query("Any updates on cases decided in 2021 or 2022?")
    assert 2021 in result["years"]
    assert 2022 in result["years"]


@pytest.mark.asyncio
async def test_normalize_query_extracts_courts():
    result = await normalize_query("What did the Bombay High Court hold on this?")
    assert any("high court" in c.lower() for c in result["courts"])


@pytest.mark.asyncio
async def test_normalize_query_always_returns_english_query():
    result = await normalize_query("simple query with no signals")
    assert result["english_query"]


@pytest.mark.asyncio
async def test_normalize_query_returns_all_expected_keys():
    result = await normalize_query("test query")
    assert set(result.keys()) == {"english_query", "sections", "acts", "years", "courts"}
