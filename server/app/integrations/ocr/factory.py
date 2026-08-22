"""Text extraction from uploaded documents.

C.1 picks Google Document AI as primary because "Indian court scans are poor". That
remains the path for scanned images, but note the split:

* **PDFs with a text layer** — extracted locally with pypdf. Most orders, chargesheets
  and cause lists downloaded from eCourts are digital PDFs, so this covers the common
  case exactly, offline, for free, and with no per-page cost. It runs before any
  provider is consulted, because paying Google to OCR a PDF that already carries its
  own text would be absurd.
* **Images and scanned PDFs** — genuinely need OCR, and go to the provider chain:
  Document AI first, then a local Tesseract install. Each provider raises when it is
  unconfigured or unavailable, so an unset key falls through to the next one instead
  of failing the document.
* **DOCX** — unzipped and read with the standard library. python-docx would be a whole
  dependency for one XML walk.

When every provider declines, the document ends `failed` with `ocr_error` explaining
which ones were tried and why each refused. A document that looks searchable but is
not is worse than one that admits it could not be read.
"""

import io
import logging
import xml.etree.ElementTree as ET
import zipfile

from app.core.config import get_settings
from app.integrations.ocr.base import OcrProvider, OcrProviderError, OcrResult
from app.integrations.ocr.document_ai import DocumentAIProvider
from app.integrations.ocr.tesseract import TesseractProvider

logger = logging.getLogger(__name__)
settings = get_settings()

# Below this, a PDF almost certainly has no text layer — it is a scan, and pypdf
# returning a handful of stray characters would look like success.
MIN_TEXT_LAYER_CHARS = 40

IMAGE_MIME_TYPES = {"image/jpeg", "image/png"}
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

# Deterministic so demo documents are searchable, and labelled loudly enough that it
# can never be mistaken for real extracted content.
FAKE_TEXT = (
    "[Demo OCR] Scanned page captured on device. "
    "Configure Google Document AI for real text extraction."
)

# `ocr_error` is a Text column, but the reasons are concatenated provider messages and
# one of them may embed an API response body.
MAX_NOTE_CHARS = 2000


async def extract_text(data: bytes, mime_type: str) -> OcrResult:
    if mime_type == "application/pdf":
        return await _extract_pdf(data)

    if mime_type in IMAGE_MIME_TYPES:
        return await run_providers(data, mime_type)

    if mime_type == DOCX_MIME:
        return _extract_docx(data)

    return OcrResult(None, "failed", f"No extractor for {mime_type}")


def providers() -> list[OcrProvider]:
    """The chain, in the order C.1 specifies. `OCR_PROVIDER` pins it to one.

    Pinning matters when a provider is configured but misbehaving: falling back would
    otherwise hide a Document AI outage behind slow, worse local results.
    """
    choice = settings.ocr_provider.strip().lower()
    if choice == "document_ai":
        return [DocumentAIProvider()]
    if choice == "tesseract":
        return [TesseractProvider()]
    if choice == "none":
        return []
    return [DocumentAIProvider(), TesseractProvider()]


async def run_providers(data: bytes, mime_type: str) -> OcrResult:
    """Tries each provider until one returns text.

    FAKE_MODE deliberately does *not* fabricate a successful extraction here, unlike
    every other integration's fake path. Those fake an outbound side effect nobody sees;
    this one would fake a claim the app displays back to the user. `ocr_status` drives
    the vault's "Searchable / Not searchable" badge, which a lawyer reads to decide
    whether a search that found nothing actually means the document is clean — so a
    green badge over placeholder text is not a harmless demo shortcut, it is the app
    lying about its own coverage. The staging instance runs FAKE_MODE=true, so this is
    the path real people see.

    Set OCR_FAKE_TEXT=true to opt in where a populated demo matters more than an honest
    badge, or to exercise the summarize/search pipeline end-to-end offline.
    """
    if settings.ocr_fake_text:
        return OcrResult(FAKE_TEXT, "done")

    reasons: list[str] = []
    for provider in providers():
        try:
            text = (await provider.extract_text(data, mime_type)).strip()
        except OcrProviderError as exc:
            logger.info("ocr provider %s declined: %s", provider.name, exc)
            reasons.append(f"{provider.name}: {exc}")
            continue

        if text:
            return OcrResult(text, "done")

        # A provider that ran and found nothing is not a success — the page may be
        # blank, but it may also be one this provider simply cannot read, which is
        # exactly what the next one is for.
        reasons.append(f"{provider.name}: found no readable text.")

    if not reasons:
        return OcrResult(None, "failed", "OCR is disabled on this server.")
    return OcrResult(None, "failed", " | ".join(reasons)[:MAX_NOTE_CHARS])


async def _extract_pdf(data: bytes) -> OcrResult:
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        pages = [page.extract_text() or "" for page in reader.pages]
        text = "\n\n".join(p.strip() for p in pages if p.strip())
    except Exception as exc:  # noqa: BLE001 - a corrupt upload must not 500 the worker
        logger.warning("pdf extraction failed: %s", exc)
        return OcrResult(None, "failed", f"This PDF could not be read: {exc}")

    if len(text) < MIN_TEXT_LAYER_CHARS:
        # A scan. This is the path that used to dead-end on "not yet wired to
        # Document AI"; it now goes to real providers.
        return await run_providers(data, "application/pdf")

    return OcrResult(text, "done")


def _extract_docx(data: bytes) -> OcrResult:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            xml = archive.read("word/document.xml")
        namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        root = ET.fromstring(xml)
        text = "\n".join(
            "".join(node.text or "" for node in para.iter(f"{namespace}t"))
            for para in root.iter(f"{namespace}p")
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("docx extraction failed: %s", exc)
        return OcrResult(None, "failed", f"This document could not be read: {exc}")

    stripped = text.strip()
    if not stripped:
        return OcrResult(None, "failed", "This document contains no text.")
    return OcrResult(stripped, "done")
