"""
Document processing pipeline (plan C.8.2):

    "confirm -> enqueue pipeline: (a) OCR ... (b) chunk ~800 tokens
    with overlap; (c) embed chunks -> pgvector; (d) ocr_status=done.
    Failures -> failed + Sentry; retry x3."

Same asyncio.run-inside-a-sync-Celery-task pattern as
app/workers/ecourts_worker.py, so Postgres RLS sees the right
`app.tenant_id` for every query.
"""

import asyncio
from uuid import UUID

import sentry_sdk
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.enums import OCRStatus
from app.db.rls import set_tenant
from app.db.session import AsyncSessionLocal
from app.integrations import storage
from app.integrations.embeddings import embed_texts
from app.integrations.ocr import extract_text
from app.models.doc_chunk import DocChunk
from app.models.document import Document
from app.services.chunking import chunk_text
from app.workers.celery_app import celery_app

logger = get_logger(__name__)


async def _set_ocr_text_vector(session: AsyncSession, document_id: UUID, raw_text: str) -> None:
    """
    Populates the tsvector search column from raw text. Done via raw
    SQL because asyncpg has no Python-str -> tsvector adapter; ORM
    attribute assignment would fail here.
    """
    await session.execute(
        text(
            "UPDATE documents SET ocr_text = to_tsvector('english', :raw_text) "
            "WHERE id = :document_id"
        ),
        {"raw_text": raw_text, "document_id": str(document_id)},
    )


async def _process_document(document_id: str, tenant_id: str) -> str:
    async with AsyncSessionLocal() as session:
        await set_tenant(session, tenant_id)

        result = await session.execute(select(Document).where(Document.id == document_id))
        document = result.scalar_one_or_none()
        if document is None:
            logger.warning("document_worker_missing_document", document_id=document_id)
            return "missing"

        try:
            document.ocr_status = OCRStatus.PROCESSING
            await session.commit()

            file_bytes = storage.get_object_bytes(document.s3_key)

            raw_text = await extract_text(
                file_bytes, document.mime_type, filename=document.name
            )

            document.extracted_text = raw_text
            await _set_ocr_text_vector(session, document.id, raw_text)

            # Replace any previous chunks (e.g. a retried/re-processed document).
            await session.execute(
                DocChunk.__table__.delete().where(DocChunk.document_id == document.id)
            )

            chunks = chunk_text(raw_text)
            if chunks:
                vectors = await embed_texts(chunks)
                for index, (chunk, vector) in enumerate(zip(chunks, vectors)):
                    session.add(
                        DocChunk(
                            tenant_id=document.tenant_id,
                            document_id=document.id,
                            chunk_index=index,
                            text=chunk,
                            embedding=vector,
                        )
                    )

            document.ocr_status = OCRStatus.COMPLETED
            document.ocr_error = None
            await session.commit()

            return "done"

        except Exception as exc:  # noqa: BLE001
            await session.rollback()

            result = await session.execute(select(Document).where(Document.id == document_id))
            document = result.scalar_one_or_none()
            if document is not None:
                document.ocr_status = OCRStatus.FAILED
                document.ocr_error = str(exc)[:2000]
                await session.commit()

            sentry_sdk.capture_exception(exc)
            logger.exception(
                "document_processing_failed", document_id=document_id, error=str(exc)
            )
            raise


@celery_app.task(
    name="app.workers.document_worker.process_document",
    bind=True,
    max_retries=3,
)
def process_document(self, document_id: str, tenant_id: str):
    try:
        return asyncio.run(_process_document(document_id, tenant_id))
    except Exception as exc:  # noqa: BLE001
        raise self.retry(exc=exc, countdown=2**self.request.retries * 30)
