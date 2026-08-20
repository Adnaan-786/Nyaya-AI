import io

from app.config import get_settings
from app.core.logging import get_logger
from app.integrations.ocr.base import OCRProviderError
from app.integrations.ocr.document_ai import DocumentAIProvider
from app.integrations.ocr.tesseract import TesseractProvider

logger = get_logger(__name__)
settings = get_settings()

_DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _extract_docx_text(file_bytes: bytes) -> str:
    """Plain extraction for DOCX (plan C.6.2) -- no OCR needed."""
    try:
        import docx
    except ImportError as exc:
        raise OCRProviderError(
            "python-docx is not installed. Run `pip install python-docx`."
        ) from exc

    document = docx.Document(io.BytesIO(file_bytes))
    return "\n".join(p.text for p in document.paragraphs if p.text.strip())


async def extract_text(file_bytes: bytes, mime_type: str, *, filename: str = "") -> str:
    """
    Runs the document-pipeline text extraction step (plan C.6.2):
      - DOCX: plain extraction, no OCR.
      - PDF/images: Document AI (primary) with a Tesseract fallback.
      - FAKE_MODE: no external calls at all, for fully offline dev/CI
        (plan C.2's "FAKE_MODE=true env switch" pattern, applied here
        the same way as MSG91/eCourts).
    """

    if settings.fake_mode:
        return (
            f"[FAKE OCR] Extracted text for {filename or 'document'} "
            f"({mime_type}). Set FAKE_MODE=false to run real extraction."
        )

    if mime_type == _DOCX_MIME:
        return _extract_docx_text(file_bytes)

    try:
        return await DocumentAIProvider().extract_text(file_bytes, mime_type)
    except (NotImplementedError, OCRProviderError) as exc:
        logger.info("ocr_falling_back_to_tesseract", reason=str(exc))

    return await TesseractProvider().extract_text(file_bytes, mime_type)
