"""C.9 contract risk review: clause segmentation and per-clause assessment."""

import pytest

from app.ai.risk_review import MAX_CLAUSES, assess_clause, review_document, segment_clauses

pytestmark = pytest.mark.asyncio

NUMBERED_CONTRACT = """
1. The Vendor shall indemnify and hold harmless the Client from any and all claims.
2. This Agreement shall terminate upon 30 days written notice by either party.
3. Payment shall be made within 15 days of invoice.
"""

PARAGRAPH_CONTRACT = """The Vendor shall indemnify and hold harmless the Client.

Payment shall be made within 15 days of invoice."""


def test_numbered_clauses_are_the_preferred_boundary() -> None:
    clauses = segment_clauses(NUMBERED_CONTRACT)

    assert len(clauses) == 3
    assert "indemnify" in clauses[0]


def test_unnumbered_text_falls_back_to_paragraphs() -> None:
    assert len(segment_clauses(PARAGRAPH_CONTRACT)) == 2


def test_text_with_no_structure_at_all_is_reviewed_whole() -> None:
    """An OCRed scan often loses its numbering, and returning nothing for it would
    report a risk-free contract."""
    assert len(segment_clauses("A single unstructured sentence with no clause markers.")) == 1


def test_empty_text_yields_no_clauses() -> None:
    assert segment_clauses("") == []
    assert segment_clauses("   ") == []


def test_clause_count_is_capped() -> None:
    many = "\n".join(f"{i}. Clause number {i} text here." for i in range(1, 100))

    assert len(segment_clauses(many)) <= MAX_CLAUSES


async def test_indemnity_language_is_flagged_high() -> None:
    result = await assess_clause("The Vendor shall indemnify the Client for all losses.")

    assert result["severity"] == "high"
    assert result["clause_text"]
    assert result["explanation"]
    assert result["suggestion"]


async def test_ordinary_payment_boilerplate_is_not_flagged() -> None:
    result = await assess_clause("Payment shall be made within 15 days of invoice.")

    assert result["severity"] == "low"


async def test_review_returns_one_row_per_clause_in_contract_shape() -> None:
    result = await review_document(NUMBERED_CONTRACT)

    assert len(result["risks"]) == 3
    for risk in result["risks"]:
        assert set(risk) == {"severity", "clause_text", "explanation", "suggestion"}
        assert risk["severity"] in ("high", "medium", "low")


async def test_empty_document_returns_no_risks() -> None:
    assert await review_document("") == {"risks": []}


async def test_an_unreadable_severity_is_treated_as_low(monkeypatch: pytest.MonkeyPatch) -> None:
    """A wall of false high-severity rows is how a lawyer learns to ignore the whole
    screen, so a malformed reply must not manufacture alarm."""

    async def _garbage(*, system: str, user: str, **kwargs) -> str:
        return "not json at all"

    monkeypatch.setattr("app.ai.risk_review.complete", _garbage)

    result = await assess_clause("The Vendor shall indemnify the Client for all losses.")

    assert result["severity"] == "low"
    assert result["clause_text"]
