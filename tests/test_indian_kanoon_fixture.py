import pytest

from app.integrations.indian_kanoon.fixture import FixtureProvider


@pytest.mark.asyncio
async def test_search_finds_relevant_fixtures_for_bail_query():
    provider = FixtureProvider()
    results = await provider.search("bail application grounds for accused", top_k=10)

    assert len(results) > 0
    doc_ids = {r.doc_id for r in results}
    # fx-001 and fx-006 are the bail-related fixtures.
    assert "fx-001" in doc_ids or "fx-006" in doc_ids


@pytest.mark.asyncio
async def test_search_returns_empty_for_gibberish_query():
    provider = FixtureProvider()
    results = await provider.search("xyzzyplugh qwertzuiop blorbnaxfoo", top_k=10)
    assert results == []


@pytest.mark.asyncio
async def test_search_respects_top_k():
    provider = FixtureProvider()
    results = await provider.search("court act section", top_k=3)
    assert len(results) <= 3


@pytest.mark.asyncio
async def test_fetch_document_returns_known_doc():
    provider = FixtureProvider()
    doc = await provider.fetch_document("fx-001")
    assert doc is not None
    assert doc.doc_id == "fx-001"
    assert doc.case_title
    assert doc.source_url.startswith("http")


@pytest.mark.asyncio
async def test_fetch_document_returns_none_for_unknown_doc():
    provider = FixtureProvider()
    doc = await provider.fetch_document("not-a-real-doc-id")
    assert doc is None


@pytest.mark.asyncio
async def test_catalog_has_twenty_fixture_cases():
    provider = FixtureProvider()
    results = await provider.search("", top_k=100)
    # empty query -> no keyword overlap -> not the right way to count;
    # instead fetch a known doc_id range to sanity check the corpus size.
    found = 0
    for i in range(1, 25):
        doc_id = f"fx-{i:03d}"
        if await provider.fetch_document(doc_id) is not None:
            found += 1
    assert found == 20
