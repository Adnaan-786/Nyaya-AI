"""The retrieval-grounded research pipeline, and the citation guarantees in it.

These run against the fixture corpus, which is exactly the point: the properties being
asserted — no citation the retrieval layer did not produce, no answer without enough
verified authority behind it — must hold whatever the corpus is.
"""

import dataclasses

import pytest

from app.ai import researcher
from app.integrations.indian_kanoon.fixture import FixtureProvider

pytestmark = pytest.mark.asyncio


async def _fixtures_by_title() -> dict:
    provider = FixtureProvider()
    found = {}
    for i in range(1, 25):
        doc = await provider.fetch_document(f"fx-{i:03d}")
        if doc is not None:
            found[doc.case_title] = doc
    return found


async def test_a_well_covered_query_returns_verified_authority() -> None:
    result = await researcher.research(query="bail application grounds for accused persons")

    assert result["confidence"] in ("high", "medium")
    assert len(result["citations"]) >= researcher.MIN_VERIFIED_CITATIONS
    assert result["answer_markdown"]


async def test_a_query_nothing_matches_returns_insufficient() -> None:
    result = await researcher.research(query="xyzzyplugh qwertzuiop blorbnaxfoo")

    assert result["confidence"] == "insufficient"
    assert result["citations"] == []
    assert "No reliable authority" in result["answer_markdown"]


async def test_result_matches_the_b7_contract_shape() -> None:
    result = await researcher.research(query="cheque dishonor notice section 138")

    assert set(result) == {"answer_markdown", "citations", "confidence"}
    for citation in result["citations"]:
        assert set(citation) == {
            "case_title",
            "court",
            "year",
            "source_url",
            "relevance_note",
        }


async def test_citation_metadata_comes_from_retrieval_and_never_from_the_model() -> None:
    """The guarantee the whole module exists for. Every field but the relevance note
    must match a retrieved document exactly, so there is no field a hallucinated case
    name could arrive in."""
    known = await _fixtures_by_title()

    result = await researcher.research(query="bail application grounds for accused persons")

    assert result["citations"], "expected this query to find authority"
    for citation in result["citations"]:
        assert citation["case_title"] in known
        real = known[citation["case_title"]]
        assert citation["court"] == real.court
        assert citation["year"] == real.year
        assert citation["source_url"] == real.source_url


async def test_too_few_verified_citations_withholds_the_answer_text_as_well(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Emptying the citation list but keeping a confident paragraph is the failure
    mode this is guarding: the proposition would still be carried into court."""

    async def _one_citation(model_citations, fragments):
        return [
            {
                "case_title": "Only One (Fixture)",
                "court": "Supreme Court of India",
                "year": 2020,
                "source_url": "https://fixtures.local/indiankanoon/fx-001",
                "relevance_note": "On point.",
            }
        ]

    monkeypatch.setattr(researcher, "_verify_citations", _one_citation)

    result = await researcher.research(query="bail application grounds for accused")

    assert result["confidence"] == "insufficient"
    assert result["citations"] == []
    assert "No reliable authority" in result["answer_markdown"]


async def test_a_citation_whose_document_has_vanished_is_dropped() -> None:
    """Verification re-fetches by document id; a judgment that is no longer in the
    index cannot be cited from a snippet we happen to still be holding."""
    fragments = await researcher._retrieve("bail application grounds")
    assert fragments

    vanished = dataclasses.replace(fragments[0], doc_id="not-a-real-doc-id")
    verified = await researcher._verify_citations(
        [{"fragment_index": 1, "relevance_note": "x"}], [vanished]
    )

    assert verified == []


async def test_a_district_court_question_carries_the_sparse_coverage_caveat() -> None:
    result = await researcher.research(
        query="maintenance case pending in district court under section 125"
    )

    if result["confidence"] != "insufficient":
        assert "sparser for district" in result["answer_markdown"]


async def test_the_language_parameter_is_accepted_end_to_end() -> None:
    """No offline provider can translate, but Hinglish input must still traverse the
    whole pipeline rather than erroring somewhere in the middle."""
    result = await researcher.research(query="bail application grounds", language="hi")

    assert result["confidence"] in ("high", "medium", "insufficient")
