"""C.9 summarizer: classification, single-pass extraction, and map-reduce."""

import pytest

from app.ai import summarizer

pytestmark = pytest.mark.asyncio

CHARGESHEET_TEXT = (
    "FIR No. 145/2026 was registered at the Andheri Police Station against "
    "the accused Ramesh Kumar under Section 302 IPC and Section 34 IPC. "
    "The chargesheet was filed on 12/03/2026 before the Chief Judicial "
    "Magistrate."
)


def _chunks(text: str, words_per_chunk: int) -> list[str]:
    words = text.split()
    return [
        " ".join(words[i : i + words_per_chunk])
        for i in range(0, len(words), words_per_chunk)
    ]


async def test_short_text_takes_the_single_pass_route() -> None:
    result = await summarizer.summarize_document(text=CHARGESHEET_TEXT, language="en")

    assert result["doc_type_detected"] == "chargesheet"
    assert "Section 302" in result["sections_invoked"]
    assert "12/03/2026" in result["dates"]
    assert result["summary_markdown"]


async def test_empty_text_returns_a_safe_default_rather_than_calling_the_model() -> None:
    result = await summarizer.summarize_document(text="", language="en")

    assert result["doc_type_detected"] == "other"
    assert result["key_points"] == []
    # Still says something: a blank summary card looks like a bug, not an empty scan.
    assert result["summary_markdown"]


async def test_long_chunked_text_is_reduced_and_capped() -> None:
    long_text = " ".join(
        f"This is filler sentence number {i} under Section {100 + i % 20} IPC "
        f"dated 0{1 + i % 9}/0{1 + i % 9}/2026."
        for i in range(400)
    )
    chunks = _chunks(long_text, 300)
    assert len(chunks) > 1

    result = await summarizer.summarize_document(text=long_text, chunks=chunks, language="en")

    assert result["summary_markdown"]
    assert len(result["sections_invoked"]) <= 20
    assert len(result["dates"]) <= 20


async def test_a_single_short_chunk_does_not_trigger_map_reduce() -> None:
    """Map-reduce costs one completion per chunk, so it must not fire on a document
    a single pass handles better anyway."""
    result = await summarizer.summarize_document(
        text=CHARGESHEET_TEXT, chunks=[CHARGESHEET_TEXT], language="en"
    )

    assert result["doc_type_detected"] == "chargesheet"


async def test_unrecognised_classification_falls_back_to_other() -> None:
    doc_type = await summarizer.detect_doc_type("The weather today is sunny and mild.")
    assert doc_type == "other"


async def test_agreement_is_detected_from_its_own_vocabulary() -> None:
    doc_type = await summarizer.detect_doc_type(
        "This agreement is entered into between the party of the first part "
        "and the party of the second part, witnesseth as follows."
    )
    assert doc_type == "agreement"
