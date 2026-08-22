"""The offline case-law corpus and the provider that searches it."""

import json

import pytest

from app.core.config import get_settings
from app.integrations import indian_kanoon
from app.integrations.indian_kanoon.fixture import FIXTURES_PATH, FixtureProvider

pytestmark = pytest.mark.asyncio


async def test_a_bail_query_finds_the_bail_fixtures() -> None:
    results = await FixtureProvider().search("bail application grounds for accused", top_k=10)

    assert results
    doc_ids = {r.doc_id for r in results}
    assert "fx-001" in doc_ids or "fx-006" in doc_ids


async def test_a_query_with_no_overlap_returns_nothing() -> None:
    """Returning the whole corpus for an unrelated question is how a researcher ends
    up citing something that has nothing to do with the case."""
    assert await FixtureProvider().search("xyzzyplugh qwertzuiop blorbnaxfoo", top_k=10) == []


async def test_top_k_is_respected() -> None:
    assert len(await FixtureProvider().search("court act section", top_k=3)) <= 3


async def test_a_known_document_can_be_fetched_for_verification() -> None:
    doc = await FixtureProvider().fetch_document("fx-001")

    assert doc is not None
    assert doc.doc_id == "fx-001"
    assert doc.case_title
    assert doc.source_url.startswith("http")


async def test_an_unknown_document_id_returns_none() -> None:
    assert await FixtureProvider().fetch_document("not-a-real-doc-id") is None


def test_the_corpus_is_labelled_as_synthetic() -> None:
    """Load-bearing, not cosmetic: nothing in here is real authority, and the file has
    to say so to whoever opens it next."""
    data = json.loads(FIXTURES_PATH.read_text(encoding="utf-8"))

    assert "synthetic" in data["_note"].lower()
    assert len(data["cases"]) == 20
    for case in data["cases"]:
        assert "(Fixture)" in case["case_title"]


def test_the_fixture_provider_is_the_default_without_a_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "fake_mode", False)
    monkeypatch.setattr(settings, "indiankanoon_api_key", None)

    assert not indian_kanoon.is_live()
    assert isinstance(indian_kanoon.get_indian_kanoon_provider(), FixtureProvider)


def test_a_configured_key_switches_to_the_real_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "fake_mode", False)
    monkeypatch.setattr(settings, "indiankanoon_api_key", "ik-test-key")

    assert indian_kanoon.is_live()
    assert not isinstance(indian_kanoon.get_indian_kanoon_provider(), FixtureProvider)


async def test_the_unimplemented_real_provider_degrades_instead_of_crashing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Setting the key before the API is written must not take a background worker
    down — the researcher handles this exception by reporting no authority found."""
    settings = get_settings()
    monkeypatch.setattr(settings, "fake_mode", False)
    monkeypatch.setattr(settings, "indiankanoon_api_key", "ik-test-key")

    provider = indian_kanoon.get_indian_kanoon_provider()

    with pytest.raises(indian_kanoon.IndianKanoonProviderError):
        await provider.search("anything", top_k=5)
