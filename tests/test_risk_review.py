import pytest

from app.ai.risk_review import segment_clauses, review_document, assess_clause

NUMBERED_CONTRACT = """
1. The Vendor shall indemnify and hold harmless the Client from any and all claims.
2. This Agreement shall terminate upon 30 days written notice by either party.
3. Payment shall be made within 15 days of invoice.
"""

PARAGRAPH_CONTRACT = """The Vendor shall indemnify and hold harmless the Client.

Payment shall be made within 15 days of invoice."""


def test_segment_clauses_splits_numbered_clauses():
    clauses = segment_clauses(NUMBERED_CONTRACT)
    assert len(clauses) == 3
    assert "indemnify" in clauses[0]


def test_segment_clauses_falls_back_to_paragraphs():
    clauses = segment_clauses(PARAGRAPH_CONTRACT)
    assert len(clauses) == 2


def test_segment_clauses_falls_back_to_whole_document():
    clauses = segment_clauses("A single unstructured sentence with no clause markers.")
    assert len(clauses) == 1


def test_segment_clauses_empty_text_returns_no_clauses():
    assert segment_clauses("") == []
    assert segment_clauses("   ") == []


def test_segment_clauses_caps_at_max_clauses():
    many_clauses = "\n".join(f"{i}. Clause number {i} text here." for i in range(1, 100))
    clauses = segment_clauses(many_clauses)
    assert len(clauses) <= 40


@pytest.mark.asyncio
async def test_assess_clause_flags_high_risk_indemnity_language():
    result = await assess_clause("The Vendor shall indemnify the Client for all losses.")
    assert result["severity"] == "high"
    assert result["clause_text"]
    assert result["explanation"]
    assert result["suggestion"]


@pytest.mark.asyncio
async def test_assess_clause_flags_low_risk_boilerplate():
    result = await assess_clause("Payment shall be made within 15 days of invoice.")
    assert result["severity"] == "low"


@pytest.mark.asyncio
async def test_review_document_returns_risks_shape():
    result = await review_document(NUMBERED_CONTRACT)

    assert "risks" in result
    assert len(result["risks"]) == 3
    for risk in result["risks"]:
        assert set(risk.keys()) == {"severity", "clause_text", "explanation", "suggestion"}
        assert risk["severity"] in ("high", "medium", "low")


@pytest.mark.asyncio
async def test_review_document_empty_text_returns_no_risks():
    result = await review_document("")
    assert result == {"risks": []}
