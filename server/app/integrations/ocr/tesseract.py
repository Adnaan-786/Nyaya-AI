"""Local Tesseract OCR — C.1's fallback provider.

Unlike Document AI this needs no account, no key and no network, which is why it is
the fallback rather than a second stub: on a host where `tesseract-ocr` (and
`poppler-utils`, for rasterising PDF pages) is installed, scanned documents genuinely
extract. Where it is not installed, the import fails and says exactly what to install.

Everything runs in a worker thread. Tesseract is CPU-bound C code with no async story,
and a 40-page scan would otherwise stall the event loop for the whole server.
"""

import asyncio
import io

from app.integrations.ocr.base import OcrProvider, OcrProviderError

SUPPORTED_IMAGE_TYPES = {"image/jpeg", "image/png"}


class TesseractProvider(OcrProvider):
    name = "Tesseract"

    async def extract_text(self, data: bytes, mime_type: str) -> str:
        return await asyncio.to_thread(self._extract, data, mime_type)

    def _extract(self, data: bytes, mime_type: str) -> str:
        try:
            import pytesseract
            from PIL import Image
        except ImportError as exc:
            raise OcrProviderError(
                f"local OCR is unavailable: {exc}. Install with: pip install "
                "pytesseract pillow pdf2image, plus the tesseract-ocr and "
                "poppler-utils system packages."
            ) from exc

        try:
            if mime_type == "application/pdf":
                pages = self._rasterise(data)
                text = "\n\n".join(pytesseract.image_to_string(page) for page in pages)
            elif mime_type in SUPPORTED_IMAGE_TYPES:
                text = pytesseract.image_to_string(Image.open(io.BytesIO(data)))
            else:
                raise OcrProviderError(f"Tesseract cannot read {mime_type}.")
        except OcrProviderError:
            raise
        except Exception as exc:  # noqa: BLE001 - a corrupt scan is a failed document
            raise OcrProviderError(f"Tesseract could not read this file: {exc}") from exc

        return text.strip()

    def _rasterise(self, data: bytes) -> list:
        """PDF pages to images. Tesseract reads pixels, not PDF."""
        try:
            from pdf2image import convert_from_bytes
        except ImportError as exc:
            raise OcrProviderError(
                f"scanned-PDF OCR is unavailable: {exc}. Install with: pip install "
                "pdf2image, plus the poppler-utils system package."
            ) from exc

        return convert_from_bytes(data)
