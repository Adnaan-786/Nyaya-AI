"""The OCR provider contract.

Providers deal only in "text, or raise". Deciding what a provider's failure *means*
for the document is the factory's job, not theirs — a provider that cannot run is
usually just the cue to try the next one, and only the factory knows whether there is
a next one.
"""

from abc import ABC, abstractmethod


class OcrProviderError(Exception):
    """A provider could not extract text.

    The message is stored in `documents.ocr_error`, so it has to say which of the two
    very different problems this is: "OCR is not configured on this server" is an
    operator's job, "this file is corrupt" is the uploader's.
    """


class OcrResult:
    """text + the `pending | done | failed` status B.5 defines, + why it failed.

    `note` is deliberately not surfaced in `DocumentOut` — the Android app has no field
    for it — but it is what makes a failed extraction diagnosable from the database.
    """

    def __init__(self, text: str | None, status: str, note: str | None = None) -> None:
        self.text = text
        self.status = status
        self.note = note


class OcrProvider(ABC):
    name: str

    @abstractmethod
    async def extract_text(self, data: bytes, mime_type: str) -> str:
        """Returns extracted text, or raises OcrProviderError."""
        raise NotImplementedError
