"""B.9 document upload, OCR and retrieval.

The three-step flow is the contract, and it exists so large scans never pass through
the API process:

1. `POST /documents/upload-url` reserves a row and returns a signed URL.
2. The app PUTs the bytes straight to that URL.
3. `POST /documents/{id}/confirm` marks it uploaded and queues OCR.

Step 3 matters: without it, an abandoned upload would leave a row claiming a file that
was never written. Only confirmed documents appear in listings.
"""

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Page, get_scoped_or_404, paginate
from app.core import envelope, security
from app.core.config import get_settings
from app.core.db import get_session, scoped
from app.integrations import storage
from app.models import Case, Client, Document
from app.schemas.documents import DocumentOut, UploadUrlOut, UploadUrlRequest
from app.services import document_service

router = APIRouter(tags=["documents"])
settings = get_settings()


def _to_out(document: Document, *, with_url: bool = True) -> dict:
    payload = DocumentOut.model_validate(document).model_dump(mode="json")
    payload["download_url"] = (
        storage.build_download_url(str(document.id))
        if with_url and document.confirmed
        else None
    )
    return payload


@router.post("/documents/upload-url")
async def create_upload_url(
    body: UploadUrlRequest,
    session: AsyncSession = Depends(get_session),
    principal: security.Principal = Depends(security.require_staff),
):
    document_service.validate_upload(body.mime_type, body.size_bytes)

    if body.case_id is not None:
        await get_scoped_or_404(session, Case, body.case_id, principal.tenant_id, "case")
    if body.client_id is not None:
        await get_scoped_or_404(session, Client, body.client_id, principal.tenant_id, "client")

    document = Document(
        tenant_id=principal.tenant_id,
        case_id=body.case_id,
        client_id=body.client_id,
        name=body.name,
        folder=body.folder,
        mime_type=body.mime_type,
        size_bytes=body.size_bytes,
        storage_key="",
        uploaded_by=principal.user_id,
        confirmed=False,
    )
    session.add(document)
    await session.flush()

    document.storage_key = storage.storage_key(
        str(principal.tenant_id), str(document.id), body.name
    )
    await session.commit()

    return envelope.ok(
        UploadUrlOut(
            upload_url=storage.build_upload_url(str(document.id)),
            document_id=document.id,
            expires_in_seconds=settings.document_upload_url_expiry_seconds,
        ).model_dump(mode="json")
    )


@router.put("/uploads/{document_id}")
async def receive_upload(
    document_id: uuid.UUID,
    request: Request,
    expires: int = Query(...),
    signature: str = Query(...),
    session: AsyncSession = Depends(get_session),
):
    """The local stand-in for an S3 presigned PUT.

    Deliberately unauthenticated in the JWT sense — the signed URL *is* the
    authorisation, exactly as with S3. That is why the signature covers the document id
    and an expiry, and why it is compared in constant time.
    """
    storage.verify_signature(str(document_id), expires, signature)

    document = await session.get(Document, document_id)
    if document is None:
        raise envelope.not_found("document")

    data = await request.body()
    # The size declared at step 1 was a claim; this is the file.
    document_service.validate_size(len(data))

    await storage.put_object(document.storage_key, data)
    # Trust the bytes actually received over the size the client predicted.
    document.size_bytes = len(data)
    await session.commit()
    return Response(status_code=200)


@router.post("/documents/{document_id}/confirm")
async def confirm_upload(
    document_id: uuid.UUID,
    background: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    principal: security.Principal = Depends(security.require_staff),
):
    """B.9 step 3: returns immediately with `ocr_status=pending`.

    OCR runs in the background because a 30-page scan takes far longer than a request
    should. The contract is explicit that no push is sent for this — the app refreshes
    document state when the vault is next viewed.
    """
    document = await get_scoped_or_404(
        session, Document, document_id, principal.tenant_id, "document"
    )
    document.confirmed = True
    document.ocr_status = "pending"
    # A re-confirmed document is being re-run; the previous reason no longer applies.
    document.ocr_error = None
    await session.commit()
    await session.refresh(document)

    background.add_task(document_service.run_ocr, document.id)
    return envelope.ok(_to_out(document))


@router.get("/documents")
async def list_documents(
    case_id: uuid.UUID | None = None,
    folder: str | None = None,
    page: Page = Depends(),
    session: AsyncSession = Depends(get_session),
    principal: security.Principal = Depends(security.require_staff),
):
    statement = scoped(Document, principal.tenant_id).where(Document.confirmed.is_(True))
    if case_id:
        statement = statement.where(Document.case_id == case_id)
    if folder:
        statement = statement.where(Document.folder == folder)
    statement = statement.order_by(Document.created_at.desc())

    rows, meta = await paginate(session, statement, page)
    return envelope.ok([_to_out(r) for r in rows], meta)


@router.get("/documents/{document_id}")
async def get_document(
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    principal: security.Principal = Depends(security.require_staff),
):
    document = await get_scoped_or_404(
        session, Document, document_id, principal.tenant_id, "document"
    )
    return envelope.ok(_to_out(document))


@router.get("/documents/{document_id}/download")
async def download_document(
    document_id: uuid.UUID,
    expires: int = Query(...),
    signature: str = Query(...),
    session: AsyncSession = Depends(get_session),
):
    """Signed-URL authorised, like the upload — this is what a viewer or a share sheet
    opens, and it must work without an Authorization header."""
    storage.verify_signature(str(document_id), expires, signature)

    document = await session.get(Document, document_id)
    if document is None or not document.confirmed:
        raise envelope.not_found("document")

    data = await storage.get_object(document.storage_key)
    return Response(
        content=data,
        media_type=document.mime_type,
        headers={"Content-Disposition": f'inline; filename="{document.name}"'},
    )


@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    principal: security.Principal = Depends(security.require_staff),
):
    document = await get_scoped_or_404(
        session, Document, document_id, principal.tenant_id, "document"
    )
    await storage.delete_object(document.storage_key)
    await session.delete(document)
    await session.commit()
    return envelope.ok({"ok": True})
