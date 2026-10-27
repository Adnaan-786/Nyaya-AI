from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import AuthContext, get_tenant_scoped_db
from app.core.rbac import require
from app.core.responses import ApiResponse, Meta
from app.schemas.invoice import InvoiceCreateIn, InvoiceFromTimeEntriesIn, InvoiceOut, InvoiceUpdateIn
from app.services import invoice_service

router = APIRouter(prefix="/invoices", tags=["Billing"])


@router.get("", response_model=ApiResponse[list[InvoiceOut]])
async def list_invoices(
    status: str | None = None,
    client_id: UUID | None = None,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    auth: AuthContext = Depends(require("billing.read")),
    session: AsyncSession = Depends(get_tenant_scoped_db),
) -> ApiResponse[list[InvoiceOut]]:
    invoices, total = await invoice_service.list_invoices(
        session, auth.as_tenant_context(), status=status, client_id=client_id,
        limit=limit, offset=(page - 1) * limit,
    )
    return ApiResponse(
        success=True,
        data=[InvoiceOut.model_validate(i) for i in invoices],
        meta=Meta(page=page, limit=limit, total=total),
    )


@router.post("", response_model=ApiResponse[InvoiceOut])
async def create_invoice(
    payload: InvoiceCreateIn,
    auth: AuthContext = Depends(require("billing.write")),
    session: AsyncSession = Depends(get_tenant_scoped_db),
) -> ApiResponse[InvoiceOut]:
    invoice = await invoice_service.create_invoice(
        session, auth.as_tenant_context(),
        client_id=payload.client_id, case_id=payload.case_id,
        line_items=[i.model_dump() for i in payload.line_items],
        gst_rate=payload.gst_rate, due_date=payload.due_date,
    )
    return ApiResponse(success=True, data=InvoiceOut.model_validate(invoice))


@router.post("/from-time-entries", response_model=ApiResponse[InvoiceOut])
async def create_invoice_from_time_entries(
    payload: InvoiceFromTimeEntriesIn,
    auth: AuthContext = Depends(require("billing.write")),
    session: AsyncSession = Depends(get_tenant_scoped_db),
) -> ApiResponse[InvoiceOut]:
    invoice = await invoice_service.create_invoice_from_time_entries(
        session, auth.as_tenant_context(), client_id=payload.client_id,
        case_id=payload.case_id, gst_rate=payload.gst_rate, due_date=payload.due_date,
    )
    return ApiResponse(success=True, data=InvoiceOut.model_validate(invoice))


@router.get("/reconciliation", response_model=ApiResponse[list[dict]])
async def reconciliation(
    auth: AuthContext = Depends(require("firm.manage")),
    session: AsyncSession = Depends(get_tenant_scoped_db),
) -> ApiResponse[list[dict]]:
    """Plan C.11.5: paid vs pending vs overdue by month, firm_admin only."""
    report = await invoice_service.reconciliation_report(session, auth.as_tenant_context())
    return ApiResponse(success=True, data=report)


@router.get("/{invoice_id}", response_model=ApiResponse[InvoiceOut])
async def get_invoice(
    invoice_id: UUID,
    auth: AuthContext = Depends(require("billing.read")),
    session: AsyncSession = Depends(get_tenant_scoped_db),
) -> ApiResponse[InvoiceOut]:
    invoice = await invoice_service.get_invoice_or_404(session, auth.as_tenant_context(), invoice_id)
    return ApiResponse(success=True, data=InvoiceOut.model_validate(invoice))


@router.patch("/{invoice_id}", response_model=ApiResponse[InvoiceOut])
async def update_invoice(
    invoice_id: UUID,
    payload: InvoiceUpdateIn,
    auth: AuthContext = Depends(require("billing.write")),
    session: AsyncSession = Depends(get_tenant_scoped_db),
) -> ApiResponse[InvoiceOut]:
    invoice = await invoice_service.get_invoice_or_404(session, auth.as_tenant_context(), invoice_id)
    items = [i.model_dump() for i in payload.line_items] if payload.line_items is not None else None
    invoice = await invoice_service.update_invoice(session, invoice, line_items=items, due_date=payload.due_date)
    return ApiResponse(success=True, data=InvoiceOut.model_validate(invoice))


@router.post("/{invoice_id}/send", response_model=ApiResponse[InvoiceOut])
async def send_invoice(
    invoice_id: UUID,
    auth: AuthContext = Depends(require("billing.write")),
    session: AsyncSession = Depends(get_tenant_scoped_db),
) -> ApiResponse[InvoiceOut]:
    tenant = auth.as_tenant_context()
    invoice = await invoice_service.get_invoice_or_404(session, tenant, invoice_id)
    invoice = await invoice_service.send_invoice(session, tenant, invoice)
    return ApiResponse(success=True, data=InvoiceOut.model_validate(invoice))


@router.get("/{invoice_id}/pdf", response_model=ApiResponse[dict])
async def get_invoice_pdf(
    invoice_id: UUID,
    auth: AuthContext = Depends(require("billing.read")),
    session: AsyncSession = Depends(get_tenant_scoped_db),
) -> ApiResponse[dict]:
    invoice = await invoice_service.get_invoice_or_404(session, auth.as_tenant_context(), invoice_id)
    return ApiResponse(success=True, data={"pdf_url": await invoice_service.get_pdf_url(invoice)})
