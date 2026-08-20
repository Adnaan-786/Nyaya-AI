import pytest

from app.ai import summarizer
from app.services.chunking import chunk_text

CHARGESHEET_TEXT = (
    "FIR No. 145/2026 was registered at the Andheri Police Station against "
    "the accused Ramesh Kumar under Section 302 IPC and Section 34 IPC. "
    "The chargesheet was filed on 12/03/2026 before the Chief Judicial "
    "Magistrate."
)


@pytest.mark.asyncio
async def test_summarize_document_short_text_single_pass():
    result = await summarizer.summarize_document(text=CHARGESHEET_TEXT, language="en")

    assert result["doc_type_detected"] == "chargesheet"
    assert "Section 302" in result["sections_invoked"]
    assert "12/03/2026" in result["dates"]
    assert result["summary_markdown"]


@pytest.mark.asyncio
async def test_summarize_document_empty_text_returns_safe_default():
    result = await summarizer.summarize_document(text="", language="en")

    assert result["doc_type_detected"] == "other"
    assert result["key_points"] == []
    assert result["summary_markdown"]


@pytest.mark.asyncio
async def test_summarize_document_long_text_uses_map_reduce():
    long_text = " ".join(
        f"This is filler sentence number {i} under Section {100 + i % 20} IPC "
        f"dated 0{1 + i % 9}/0{1 + i % 9}/2026."
        for i in range(400)
    )
    chunks = chunk_text(long_text, chunk_words=300, overlap_words=30)
    assert len(chunks) > 1

    result = await summarizer.summarize_document(text=long_text, chunks=chunks, language="en")

    assert result["summary_markdown"]
    assert len(result["sections_invoked"]) <= 20
    assert len(result["dates"]) <= 20


@pytest.mark.asyncio
async def test_summarize_document_short_text_skips_map_reduce_even_with_chunks():
    """A single short chunk shouldn't trigger the (more expensive) map-reduce path."""
    chunks = [CHARGESHEET_TEXT]
    result = await summarizer.summarize_document(
        text=CHARGESHEET_TEXT, chunks=chunks, language="en"
    )
    assert result["doc_type_detected"] == "chargesheet"


@pytest.mark.asyncio
async def test_detect_doc_type_direct():
    doc_type = await summarizer.detect_doc_type(
        "This agreement is entered into between the party of the first part "
        "and the party of the second part, witnesseth as follows."
    )
    assert doc_type == "agreement"
