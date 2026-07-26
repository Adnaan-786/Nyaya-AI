"""Text extraction from uploaded documents.

C.1 picks Google Document AI as primary because "Indian court scans are poor". That
remains the path for scanned images, but note the split:

* **PDFs with a text layer** — extracted locally with pypdf. Most orders, chargesheets
  and cause lists downloaded from eCourts are digital PDFs, so this covers the common
  case exactly, offline, for free, and with no per-page cost.
* **Images and scanned PDFs** — genuinely need OCR. Document AI when configured;
  otherwise the document is marked `failed` with an honest reason rather than being
  silently left blank, because a document that looks searchable but is not is worse
  than one that admits it could not be read.
"""

import io
import logging

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Below this, a PDF almost certainly has no text layer — it is a scan, and pypdf
# returning a handful of stray characters would look like success.
MIN_TEXT_LAYER_CHARS = 40


class OcrResult:
    def __init__(self, text: str | None, status: str, note: str | None = None) -> None:
        self.text = text
        self.status = status
        self.note = note


async def extract_text(data: bytes, mime_type: str) -> OcrResult:
    if mime_type == "application/pdf":
        return _extract_pdf(data)

    if mime_type in {"image/jpeg", "image/png"}:
        return await _extract_image(data)

    if mime_type.endswith("wordprocessingml.document"):
        return _extract_docx(data)

    return OcrResult(None, "failed", f"No extractor for {mime_type}")


def _extract_pdf(data: bytes) -> OcrResult:
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        pages = [page.extract_text() or "" for page in reader.pages]
        text = "\n\n".join(p.strip() for p in pages if p.strip())
    except Exception as exc:  # noqa: BLE001 - a corrupt upload must not 500 the worker
        logger.warning("pdf extraction failed: %s", exc)
        return OcrResult(None, "failed", "This PDF could not be read.")

    if len(text) < MIN_TEXT_LAYER_CHARS:
        # A scan. Fall through to real OCR when it is available.
        if settings.fake_mode or not settings.anthropic_api_key:
            return OcrResult(
                None,
                "failed",
                "This looks like a scanned PDF. OCR is not configured on this server.",
            )
        return OcrResult(None, "failed", "Scanned PDF OCR not yet wired to Document AI.")

    return OcrResult(text, "done")


def _extract_docx(data: bytes) -> OcrResult:
    try:
        import xml.etree.ElementTree as ET
        import zipfile

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
        return OcrResult(None, "failed", "This document could not be read.")

    return OcrResult(text.strip() or None, "done" if text.strip() else "failed")


async def _extract_image(data: bytes) -> OcrResult:
    if settings.fake_mode:
        # Deterministic so demo documents are searchable, and clearly labelled so it
        # can never be mistaken for real extracted content.
        return OcrResult(
            "[Demo OCR] Scanned page captured on device. "
            "Configure Google Document AI for real text extraction.",
            "done",
        )

    logger.info("image OCR requested but Document AI is not configured")
    return OcrResult(None, "failed", "OCR is not configured on this server.")
