import asyncio
import io

from app.integrations.ocr.base import OCRProvider, OCRProviderError

_SUPPORTED_IMAGE_TYPES = {"image/png", "image/jpeg"}


class TesseractProvider(OCRProvider):
    """
    Local, no-credentials-needed OCR fallback (plan C.1). Requires the
    system `tesseract-ocr` binary (and `poppler-utils` for PDF page
    rasterization) to be installed -- see the Dockerfile. Both are
    plain open-source packages, not a paid/keyed API, so unlike
    Document AI/NAPIX/commercial-eCourts this is safe to implement for
    real today.
    """

    async def extract_text(self, file_bytes: bytes, mime_type: str) -> str:
        return await asyncio.to_thread(self._extract_sync, file_bytes, mime_type)

    def _extract_sync(self, file_bytes: bytes, mime_type: str) -> str:
        try:
            import pytesseract
            from PIL import Image
        except ImportError as exc:
            raise OCRProviderError(
                "pytesseract/Pillow are not installed. Run "
                "`pip install pytesseract pillow pdf2image` and install "
                "the tesseract-ocr (+ poppler-utils for PDFs) system packages."
            ) from exc

        try:
            if mime_type == "application/pdf":
                text = self._extract_pdf(file_bytes, pytesseract, Image)
            elif mime_type in _SUPPORTED_IMAGE_TYPES:
                image = Image.open(io.BytesIO(file_bytes))
                text = pytesseract.image_to_string(image)
            else:
                raise OCRProviderError(
                    f"Tesseract fallback does not support mime_type={mime_type!r}"
                )
        except OCRProviderError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise OCRProviderError(f"Tesseract OCR failed: {exc}") from exc

        return text.strip()

    def _extract_pdf(self, file_bytes: bytes, pytesseract, Image) -> str:
        try:
            from pdf2image import convert_from_bytes
        except ImportError as exc:
            raise OCRProviderError(
                "pdf2image is not installed (needed for scanned-PDF OCR). "
                "Run `pip install pdf2image` and install poppler-utils."
            ) from exc

        pages = convert_from_bytes(file_bytes)
        page_texts = [pytesseract.image_to_string(page) for page in pages]
        return "\n\n".join(page_texts)
