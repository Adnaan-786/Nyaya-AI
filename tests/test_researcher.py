import pytest

from app.ai import researcher


@pytest.mark.asyncio
async def test_research_relevant_query_returns_high_or_medium_confidence():
    result = await researcher.research(query="bail application grounds for accused persons")

    assert result["confidence"] in ("high", "medium")
    assert len(result["citations"]) >= 2
    assert result["answer_markdown"]


@pytest.mark.asyncio
async def test_research_gibberish_query_returns_insufficient():
    result = await researcher.research(query="xyzzyplugh qwertzuiop blorbnaxfoo")

    assert result["confidence"] == "insufficient"
    assert result["citations"] == []
    assert "No reliable authority" in result["answer_markdown"]


@pytest.mark.asyncio
async def test_research_result_matches_contract_shape():
    result = await researcher.research(query="cheque dishonor notice section 138")

    assert set(result.keys()) == {"answer_markdown", "citations", "confidence"}
    for citation in result["citations"]:
        assert set(citation.keys()) == {
            "case_title", "court", "year", "source_url", "relevance_note",
        }


@pytest.mark.asyncio
async def test_research_citation_metadata_comes_from_retrieval_not_llm():
    """
    Every returned citation's case_title/court/year/source_url must
    exactly match a real fixture entry -- the LLM only picks which
    fragments it used, it never gets to invent citation metadata.
    """
    from app.integrations.indian_kanoon.fixture import FixtureProvider

    provider = FixtureProvider()
    all_fixtures = {}
    for i in range(1, 25):
        doc = await provider.fetch_document(f"fx-{i:03d}")
        if doc:
            all_fixtures[doc.case_title] = doc

    result = await researcher.research(query="rent eviction landlord tenant")

    for citation in result["citations"]:
        assert citation["case_title"] in all_fixtures
        real = all_fixtures[citation["case_title"]]
        assert citation["court"] == real.court
        assert citation["year"] == real.year
        assert citation["source_url"] == real.source_url


@pytest.mark.asyncio
async def test_research_district_court_query_gets_sparse_coverage_note():
    result = await researcher.research(
        query="maintenance case pending in district court under section 125"
    )

    if result["confidence"] != "insufficient":
        assert "sparser for district" in result["answer_markdown"]


@pytest.mark.asyncio
async def test_research_mirrors_requested_language_field():
    # FAKE_MODE can't actually translate, but the pipeline must still
    # accept and pass through the language parameter without erroring.
    result = await researcher.research(
        query="bail application grounds", language="hi"
    )
    assert result["confidence"] in ("high", "medium", "insufficient")
