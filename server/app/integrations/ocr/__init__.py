"""OCR provider abstraction (C.1).

`extract_text` and `OcrResult` are the whole public surface, unchanged from when this
was a single module — app/services/document_service.py imports exactly those two.
"""

from app.integrations.ocr.base import OcrProvider, OcrProviderError, OcrResult
from app.integrations.ocr.document_ai import DocumentAIProvider
from app.integrations.ocr.factory import extract_text, providers
from app.integrations.ocr.tesseract import TesseractProvider

__all__ = [
    "DocumentAIProvider",
    "OcrProvider",
    "OcrProviderError",
    "OcrResult",
    "TesseractProvider",
    "extract_text",
    "providers",
]
