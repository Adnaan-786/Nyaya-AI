from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import AuthContext, get_tenant_scoped_db
from app.core.rbac import require
from app.core.responses import ApiResponse, Meta
from app.schemas.document import DocumentOut, DocumentUploadUrlIn, DocumentUploadUrlOut
from app.services import audit_service, document_service

router = APIRouter(prefix="/documents", tags=["Documents"])


def _document_out(document, *, download_url: str | None = None) -> DocumentOut:
    data = DocumentOut.model_validate(document).model_dump()
    data["download_url"] = download_url
    return DocumentOut(**data)


@router.post("/upload-url", response_model=ApiResponse[DocumentUploadUrlOut])
async def request_upload_url(
    payload: DocumentUploadUrlIn,
    auth: AuthContext = Depends(require("documents.write")),
    session: AsyncSession = Depends(get_tenant_scoped_db),
) -> ApiResponse[DocumentUploadUrlOut]:
    tenant = auth.as_tenant_context()
    document, upload_url = await document_service.request_upload_url(
        session,
        tenant,
        name=payload.name,
        mime_type=payload.mime_type,
        size_bytes=payload.size_bytes,
        case_id=payload.case_id,
        client_id=payload.client_id,
        folder=payload.folder,
        uploaded_by=auth.user_id,
    )
    return ApiResponse(
        success=True,
        data=DocumentUploadUrlOut(upload_url=upload_url, document_id=document.id),
    )


@router.post("/{document_id}/confirm", response_model=ApiResponse[DocumentOut])
async def confirm_upload(
    document_id: UUID,
    auth: AuthContext = Depends(require("documents.write")),
    session: AsyncSession = Depends(get_tenant_scoped_db),
) -> ApiResponse[DocumentOut]:
    tenant = auth.as_tenant_context()
    document = await document_service.get_document_or_404(session, tenant, document_id)
    document = await document_service.confirm_upload(session, document)
    return ApiResponse(success=True, data=_document_out(document))


@router.get("", response_model=ApiResponse[list[DocumentOut]])
async def list_documents(
    case_id: UUID | None = None,
    folder: str | None = None,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    auth: AuthContext = Depends(require("documents.read")),
    session: AsyncSession = Depends(get_tenant_scoped_db),
) -> ApiResponse[list[DocumentOut]]:
    tenant = auth.as_tenant_context()
    documents, total = await document_service.list_documents(
        session, tenant, case_id=case_id, folder=folder, limit=limit, offset=(page - 1) * limit
    )
    return ApiResponse(
        success=True,
        data=[_document_out(d) for d in documents],
        meta=Meta(page=page, limit=limit, total=total),
    )


@router.get("/{document_id}", response_model=ApiResponse[DocumentOut])
async def get_document(
    document_id: UUID,
    request: Request,
    auth: AuthContext = Depends(require("documents.read")),
    session: AsyncSession = Depends(get_tenant_scoped_db),
) -> ApiResponse[DocumentOut]:
    tenant = auth.as_tenant_context()
    document = await document_service.get_document_or_404(session, tenant, document_id)
    download_url = document_service.build_download_url(document)

    # contract B.6/C.8: "download_url ... audit-logged (who downloaded
    # what when -- lawyers care deeply)".
    await audit_service.write_audit(
        session,
        tenant_id=tenant.tenant_id,
        actor_id=auth.user_id,
        action="document.download_url_issued",
        entity_type="document",
        entity_id=str(document.id),
        request=request,
    )
    await session.commit()

    return ApiResponse(success=True, data=_document_out(document, download_url=download_url))


@router.delete("/{document_id}", response_model=ApiResponse[dict])
async def delete_document(
    document_id: UUID,
    auth: AuthContext = Depends(require("documents.delete")),
    session: AsyncSession = Depends(get_tenant_scoped_db),
) -> ApiResponse[dict]:
    tenant = auth.as_tenant_context()
    document = await document_service.get_document_or_404(session, tenant, document_id)
    await document_service.delete_document(session, document)
    return ApiResponse(success=True, data={"deleted": True})
