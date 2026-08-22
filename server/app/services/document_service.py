"""Document pipeline internals behind the B.9 routes.

The routes in app/api/documents.py own the HTTP contract; this owns what happens
around it — what an upload is allowed to be, and what turns its bytes into text.
Keeping the two apart matters most for OCR, which runs after the response has already
gone out and therefore cannot signal anything by raising.
"""

import logging
import uuid

from app.core import envelope
from app.core.config import get_settings
from app.core.db import SessionFactory
from app.integrations import ocr, storage
from app.models import Document

logger = logging.getLogger(__name__)
settings = get_settings()

# `ocr_error` is unbounded Text, but the reasons are concatenated provider messages and
# an unexpected exception can carry a whole SQL statement with it.
MAX_ERROR_CHARS = 2000


def validate_upload(mime_type: str, size_bytes: int) -> None:
    """B.9's limits, checked before a row is reserved.

    The size here is the one the client *claims*, so `validate_size` runs again on the
    PUT against the bytes that actually arrived. This earlier check exists so the
    common case fails fast, with a message about the file rather than about a rejected
    upload.
    """
    if mime_type not in settings.document_allowed_mime_type_set:
        raise envelope.validation(
            "That file type is not supported.", {"mime_type": mime_type}
        )
    if size_bytes <= 0:
        raise envelope.validation(
            "That file is empty.", {"size_bytes": str(size_bytes)}
        )
    validate_size(size_bytes)


def upload_limit_bytes() -> int:
    """The lower of the document limit and the global one.

    Two settings because they answer different questions — B.9's per-document cap, and
    the host's cap on any request body — but only the smaller one can ever apply, and
    quietly ignoring a deployment that has tightened `MAX_UPLOAD_BYTES` would be a
    surprising way to find out.
    """
    return min(settings.document_max_upload_bytes, settings.max_upload_bytes)


def validate_size(size_bytes: int) -> None:
    limit = upload_limit_bytes()
    if size_bytes > limit:
        raise envelope.validation(
            f"Files must be smaller than {limit // (1024 * 1024)} MB.",
            {"size_bytes": str(size_bytes)},
        )


async def run_ocr(document_id: uuid.UUID) -> None:
    """B.9 step 3's background half. Opens its own session — the request's is closed.

    Ends in `done` or `failed`, never `processing`: the app's OcrStatus enum knows
    three values plus UNKNOWN, so an intermediate state would render as an unlabelled
    badge on a document that is working fine.
    """
    async with SessionFactory() as session:
        document = await session.get(Document, document_id)
        if document is None:
            return

        try:
            data = await storage.get_object(document.storage_key)
            result = await ocr.extract_text(data, document.mime_type)
        except Exception as exc:  # noqa: BLE001 - a failed extraction must not lose the file
            logger.exception("ocr failed for document %s", document_id)
            document.ocr_status = "failed"
            document.ocr_error = (str(exc) or exc.__class__.__name__)[:MAX_ERROR_CHARS]
            await session.commit()
            return

        document.ocr_text = result.text
        document.ocr_status = result.status
        # Cleared on success, so a document that failed once and was re-run does not
        # keep explaining a problem it no longer has.
        document.ocr_error = result.note[:MAX_ERROR_CHARS] if result.note else None
        await session.commit()
