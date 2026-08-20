from abc import ABC, abstractmethod


class OCRProviderError(Exception):
    """Raised when an OCR provider fails to extract text."""


class OCRProvider(ABC):
    @abstractmethod
    async def extract_text(self, file_bytes: bytes, mime_type: str) -> str:
        """Returns extracted plain text, or raises OCRProviderError."""
        raise NotImplementedError
