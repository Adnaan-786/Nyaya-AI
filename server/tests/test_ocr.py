"""C.1 text extraction, and the honesty of its failure modes.

The load-bearing property is that a document never ends up looking searchable when it
is not: an unconfigured provider must produce `failed` with a reason, not `done` with
nothing in it, and never an exception that loses the file.
"""

import io
import zipfile

import pytest

from app.core.config import get_settings
from app.integrations import ocr
from app.integrations.ocr import DocumentAIProvider, OcrProviderError, TesseractProvider
from app.integrations.ocr import factory as ocr_factory
from tests.test_documents import _pdf

settings = get_settings()

# A structurally valid PDF whose only content stream draws no glyphs — what a scan
# looks like to pypdf.
SCANNED_PDF = _pdf([])
TEXT_PDF = _pdf(["IN THE HIGH COURT OF KARNATAKA AT BENGALURU", "ORDER SHEET"])


def _docx(paragraphs: list[str]) -> bytes:
    namespace = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    body = "".join(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paragraphs)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(
            "word/document.xml",
            f'<?xml version="1.0"?><w:document xmlns:w="{namespace}">'
            f"<w:body>{body}</w:body></w:document>",
        )
    return buffer.getvalue()


@pytest.fixture
def live(monkeypatch: pytest.MonkeyPatch) -> None:
    """FAKE_MODE off, so the provider chain actually runs."""
    monkeypatch.setattr(settings, "fake_mode", False)


async def test_a_pdf_with_a_text_layer_never_reaches_a_provider(live: None) -> None:
    """The common case — an eCourts download — costs nothing and works offline, even
    with every OCR provider unconfigured."""
    result = await ocr.extract_text(TEXT_PDF, "application/pdf")

    assert result.status == "done"
    assert "KARNATAKA" in result.text
    assert result.note is None


async def test_a_scan_with_no_provider_configured_fails_with_a_reason(live: None) -> None:
    result = await ocr.extract_text(SCANNED_PDF, "application/pdf")

    assert result.status == "failed"
    assert result.text is None
    assert "Document AI" in result.note


async def test_an_image_with_no_provider_configured_fails_with_a_reason(live: None) -> None:
    result = await ocr.extract_text(b"not really a jpeg", "image/jpeg")

    assert result.status == "failed"
    assert result.text is None
    assert result.note


async def test_ocr_can_be_turned_off_outright(
    live: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "ocr_provider", "none")

    result = await ocr.extract_text(SCANNED_PDF, "application/pdf")

    assert result.status == "failed"
    assert result.note == "OCR is disabled on this server."


@pytest.mark.parametrize(
    ("choice", "expected"),
    [
        ("auto", ["Document AI", "Tesseract"]),
        ("document_ai", ["Document AI"]),
        ("tesseract", ["Tesseract"]),
        ("none", []),
    ],
)
def test_the_provider_chain_follows_the_setting(
    choice: str, expected: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "ocr_provider", choice)
    assert [p.name for p in ocr.providers()] == expected


async def test_unconfigured_document_ai_declines_instead_of_crashing() -> None:
    with pytest.raises(OcrProviderError) as raised:
        await DocumentAIProvider().extract_text(b"bytes", "application/pdf")

    # The message has to name what to set — it is what lands in `ocr_error`.
    assert "DOCUMENT_AI_PROJECT_ID" in str(raised.value)


async def test_document_ai_refuses_a_file_too_large_for_the_sync_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Better a clear refusal than a 20 MB upload to Google that is rejected there."""
    monkeypatch.setattr(settings, "document_ai_project_id", "p")
    monkeypatch.setattr(settings, "document_ai_processor_id", "proc")
    monkeypatch.setattr(settings, "google_credentials_path", "/nonexistent.json")

    with pytest.raises(OcrProviderError) as raised:
        await DocumentAIProvider().extract_text(b"x" * (21 * 1024 * 1024), "application/pdf")

    assert "20 MB" in str(raised.value)


async def test_misconfigured_document_ai_credentials_decline_instead_of_crashing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "document_ai_project_id", "p")
    monkeypatch.setattr(settings, "document_ai_processor_id", "proc")
    monkeypatch.setattr(settings, "google_credentials_path", "/nonexistent.json")

    with pytest.raises(OcrProviderError):
        await DocumentAIProvider().extract_text(b"bytes", "application/pdf")


async def test_tesseract_declines_a_type_it_cannot_read() -> None:
    with pytest.raises(OcrProviderError):
        await TesseractProvider().extract_text(b"bytes", "text/plain")


async def test_a_corrupt_pdf_fails_without_raising(live: None) -> None:
    result = await ocr.extract_text(b"%PDF-1.4 truncated", "application/pdf")

    assert result.status == "failed"
    assert result.note


async def test_docx_is_read_with_the_standard_library(live: None) -> None:
    """No provider, no python-docx — a DOCX is a zip with one XML file in it."""
    data = _docx(["MEMORANDUM OF UNDERSTANDING", "Executed at Bengaluru."])

    result = await ocr.extract_text(
        data, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )

    assert result.status == "done"
    assert "MEMORANDUM" in result.text
    assert "Bengaluru" in result.text


async def test_an_empty_docx_fails_rather_than_reporting_done(live: None) -> None:
    result = await ocr.extract_text(
        _docx([]),
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

    assert result.status == "failed"
    assert result.text is None


async def test_an_unknown_type_names_itself_in_the_reason(live: None) -> None:
    result = await ocr.extract_text(b"bytes", "application/zip")

    assert result.status == "failed"
    assert "application/zip" in result.note


async def test_fake_mode_does_not_claim_a_scan_is_searchable() -> None:
    """FAKE_MODE fakes side effects, not findings.

    `ocr_status` is rendered to the user as "Searchable / Not searchable", and a lawyer
    reads it to decide whether an empty search result means the document is clean. A
    green badge over placeholder text would make the app misreport its own coverage on
    the staging instance, which runs FAKE_MODE=true.
    """
    for data, mime_type in ((SCANNED_PDF, "application/pdf"), (b"x", "image/png")):
        result = await ocr.extract_text(data, mime_type)
        assert result.status == "failed"
        assert result.text is None


async def test_the_placeholder_is_opt_in_and_labelled_loudly(monkeypatch) -> None:
    """Opting in is still allowed — for exercising summarize/search offline — but the
    text has to be impossible to mistake for something the server actually read."""
    monkeypatch.setattr(ocr_factory.settings, "ocr_fake_text", True)

    result = await ocr.extract_text(SCANNED_PDF, "application/pdf")

    assert result.status == "done"
    assert result.text.startswith("[Demo OCR]")


async def test_fake_mode_still_extracts_a_real_text_layer() -> None:
    """Offline does not mean fabricated: pypdf runs regardless, which is why the demo
    vault is genuinely searchable."""
    result = await ocr.extract_text(TEXT_PDF, "application/pdf")

    assert "KARNATAKA" in result.text
