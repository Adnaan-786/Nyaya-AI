from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import ValidationException
from app.db.enums import OCRStatus
from app.db.tenant import TenantContext
from app.integrations import storage
from app.models.document import Document

settings = get_settings()


def validate_upload_request(*, mime_type: str, size_bytes: int) -> None:
    if size_bytes > settings.document_max_upload_bytes:
        raise ValidationException(
            "File exceeds the maximum upload size.",
            details={
                "max_bytes": settings.document_max_upload_bytes,
                "given_bytes": size_bytes,
            },
        )

    if mime_type not in settings.document_allowed_mime_type_set:
        raise ValidationException(
            "Unsupported file type.",
            details={
                "mime_type": mime_type,
                "allowed": sorted(settings.document_allowed_mime_type_set),
            },
        )


async def request_upload_url(
    session: AsyncSession,
    tenant: TenantContext,
    *,
    name: str,
    mime_type: str,
    size_bytes: int,
    case_id: UUID | None,
    client_id: UUID | None,
    folder: str | None,
    uploaded_by: UUID,
) -> tuple[Document, str]:
    """POST /documents/upload-url (contract B.9 step 1)."""
    validate_upload_request(mime_type=mime_type, size_bytes=size_bytes)

    document = Document(
        tenant_id=tenant.tenant_id,
        case_id=case_id,
        client_id=client_id,
        name=name,
        folder=folder,
        mime_type=mime_type,
        size_bytes=size_bytes,
        s3_key="",  # filled in below, once we have the document id
        ocr_status=OCRStatus.PENDING,
        uploaded_by=uploaded_by,
    )
    session.add(document)
    await session.flush()  # assigns document.id

    document.s3_key = storage.object_key_for(tenant.tenant_id, document.id, name)
    await session.commit()
    await session.refresh(document)

    upload_url = storage.generate_presigned_upload_url(document.s3_key, mime_type)

    return document, upload_url


async def get_document_or_404(
    session: AsyncSession, tenant: TenantContext, document_id: UUID
) -> Document:
    result = await session.execute(
        select(Document)
        .where(Document.id == document_id)
        .where(Document.tenant_id == tenant.tenant_id)
    )
    document = result.scalar_one_or_none()
    if document is None:
        raise ValidationException("Document not found.")
    return document


async def confirm_upload(session: AsyncSession, document: Document) -> Document:
    """
    POST /documents/{id}/confirm (contract B.9 step 3): the file bytes
    are already in S3 by now (the app PUT them directly per step 2).
    This just enqueues the processing pipeline; see
    app/workers/document_worker.py::process_document.
    """
    from app.workers.document_worker import process_document

    document.ocr_status = OCRStatus.PENDING
    await session.commit()
    await session.refresh(document)

    process_document.delay(str(document.id), str(document.tenant_id))

    return document


async def list_documents(
    session: AsyncSession,
    tenant: TenantContext,
    *,
    case_id: UUID | None = None,
    folder: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[Document], int]:
    stmt = select(Document).where(Document.tenant_id == tenant.tenant_id)
    count_stmt = select(Document.id).where(Document.tenant_id == tenant.tenant_id)

    if case_id:
        stmt = stmt.where(Document.case_id == case_id)
        count_stmt = count_stmt.where(Document.case_id == case_id)

    if folder:
        stmt = stmt.where(Document.folder == folder)
        count_stmt = count_stmt.where(Document.folder == folder)

    total = len((await session.execute(count_stmt)).all())

    stmt = stmt.order_by(Document.created_at.desc()).limit(limit).offset(offset)
    result = await session.execute(stmt)

    return list(result.scalars().all()), total


def build_download_url(document: Document) -> str:
    return storage.generate_presigned_download_url(document.s3_key, filename=document.name)


async def delete_document(session: AsyncSession, document: Document) -> None:
    storage.delete_object(document.s3_key)
    await session.delete(document)
    await session.commit()
