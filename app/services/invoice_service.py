from datetime import date
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import ValidationException
from app.core.security import utcnow
from app.db.enums import InvoiceStatus, NotificationType
from app.db.tenant import TenantContext
from app.integrations import razorpay, storage
from app.models.client import Client
from app.models.invoice import Invoice
from app.models.tenant import Tenant
from app.models.time_entry import TimeEntry
from app.services.invoice_pdf import render_invoice_pdf
from app.services.notification_dispatch_service import notify

settings = get_settings()


def compute_gst(subtotal_paise: int, gst_rate: int) -> int:
    """Contract B.1: money is integer paise; GST is computed on the subtotal."""
    return round(subtotal_paise * gst_rate / 100)


def normalize_line_items(line_items: list[dict]) -> tuple[list[dict], int]:
    """Recomputes amount_paise = qty * rate_paise server-side (never trust client totals)."""
    normalized, subtotal = [], 0
    for item in line_items:
        amount = round(item["qty"] * item["rate_paise"])
        normalized.append(
            {
                "description": item["description"],
                "qty": item["qty"],
                "rate_paise": item["rate_paise"],
                "amount_paise": amount,
            }
        )
        subtotal += amount
    return normalized, subtotal


def next_invoice_number(existing_max: str | None, year: int) -> str:
    """INV-2026-0001 style, sequential per tenant per year (plan C.11.1)."""
    prefix = f"INV-{year}-"
    seq = 1
    if existing_max:
        try:
            seq = int(existing_max.split("-")[-1]) + 1
        except ValueError:
            seq = 1
    return f"{prefix}{seq:04d}"


async def generate_invoice_number(session: AsyncSession, tenant_id: UUID) -> str:
    # Max-existing + 1 is fine at expected volumes; high concurrent
    # creation would want a DB sequence or advisory lock to fully rule
    # out two requests picking the same number.
    year = utcnow().year
    result = await session.execute(
        select(func.max(Invoice.number))
        .where(Invoice.tenant_id == tenant_id)
        .where(Invoice.number.like(f"INV-{year}-%"))
    )
    return next_invoice_number(result.scalar_one_or_none(), year)


async def create_invoice(
    session: AsyncSession,
    tenant: TenantContext,
    *,
    client_id: UUID,
    case_id: UUID | None,
    line_items: list[dict],
    gst_rate: int | None,
    due_date: date | None,
) -> Invoice:
    gst_rate = settings.invoice_default_gst_rate if gst_rate is None else gst_rate
    if gst_rate not in (0, settings.invoice_default_gst_rate):
        raise ValidationException(
            "gst_rate must be 0 or the configured default rate.",
            details={"allowed": [0, settings.invoice_default_gst_rate]},
        )

    items, subtotal = normalize_line_items(line_items)
    if subtotal <= 0:
        raise ValidationException("Invoice must have at least one line item with a positive amount.")

    gst = compute_gst(subtotal, gst_rate)
    invoice = Invoice(
        tenant_id=tenant.tenant_id,
        number=await generate_invoice_number(session, tenant.tenant_id),
        client_id=client_id,
        case_id=case_id,
        line_items=items,
        subtotal_paise=subtotal,
        gst_rate=gst_rate,
        gst_paise=gst,
        total_paise=subtotal + gst,
        status=InvoiceStatus.DRAFT,
        due_date=due_date,
    )
    session.add(invoice)
    await session.commit()
    await session.refresh(invoice)
    return invoice


async def create_invoice_from_time_entries(
    session: AsyncSession,
    tenant: TenantContext,
    *,
    client_id: UUID,
    case_id: UUID,
    gst_rate: int | None,
    due_date: date | None,
) -> Invoice:
    """Plan C.11.1: line items from unbilled, billable time entries for a case."""
    result = await session.execute(
        select(TimeEntry)
        .where(TimeEntry.case_id == case_id)
        .where(TimeEntry.tenant_id == tenant.tenant_id)
        .where(TimeEntry.billable.is_(True))
        .where(TimeEntry.invoice_id.is_(None))
    )
    unbilled = list(result.scalars().all())
    if not unbilled:
        raise ValidationException("No unbilled time entries found for this case.")

    line_items = []
    for entry in unbilled:
        if entry.rate_paise is None:
            raise ValidationException(
                "Time entry has no rate_paise set; cannot bill it.",
                details={"time_entry_id": str(entry.id)},
            )
        line_items.append(
            {
                "description": entry.description or f"Time entry {entry.date.isoformat()}",
                "qty": round(entry.duration_minutes / 60, 2),
                "rate_paise": entry.rate_paise,
            }
        )

    invoice = await create_invoice(
        session, tenant, client_id=client_id, case_id=case_id,
        line_items=line_items, gst_rate=gst_rate, due_date=due_date,
    )
    for entry in unbilled:
        entry.invoice_id = invoice.id
    await session.commit()
    await session.refresh(invoice)
    return invoice


async def get_invoice_or_404(session: AsyncSession, tenant: TenantContext, invoice_id: UUID) -> Invoice:
    result = await session.execute(
        select(Invoice).where(Invoice.id == invoice_id).where(Invoice.tenant_id == tenant.tenant_id)
    )
    invoice = result.scalar_one_or_none()
    if invoice is None:
        raise ValidationException("Invoice not found.")
    return invoice


async def list_invoices(
    session: AsyncSession,
    tenant: TenantContext,
    *,
    status: str | None = None,
    client_id: UUID | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[Invoice], int]:
    stmt = select(Invoice).where(Invoice.tenant_id == tenant.tenant_id)
    count_stmt = select(Invoice.id).where(Invoice.tenant_id == tenant.tenant_id)
    if status:
        stmt, count_stmt = stmt.where(Invoice.status == status), count_stmt.where(Invoice.status == status)
    if client_id:
        stmt, count_stmt = stmt.where(Invoice.client_id == client_id), count_stmt.where(Invoice.client_id == client_id)

    total = len((await session.execute(count_stmt)).all())
    result = await session.execute(stmt.order_by(Invoice.created_at.desc()).limit(limit).offset(offset))
    return list(result.scalars().all()), total


async def update_invoice(session: AsyncSession, invoice: Invoice, *, line_items, due_date) -> Invoice:
    if invoice.status != InvoiceStatus.DRAFT:
        raise ValidationException("Only draft invoices can be edited.")
    if due_date is not None:
        invoice.due_date = due_date
    if line_items is not None:
        items, subtotal = normalize_line_items(line_items)
        invoice.line_items = items
        invoice.subtotal_paise = subtotal
        invoice.gst_paise = compute_gst(subtotal, invoice.gst_rate)
        invoice.total_paise = subtotal + invoice.gst_paise
    await session.commit()
    await session.refresh(invoice)
    return invoice


async def send_invoice(session: AsyncSession, tenant: TenantContext, invoice: Invoice) -> Invoice:
    """Plan C.11.2-3: render + upload the PDF, create a Razorpay payment link, notify the client."""
    if invoice.status not in (InvoiceStatus.DRAFT, InvoiceStatus.SENT):
        raise ValidationException("Only draft or already-sent invoices can be (re)sent.")

    client = (await session.execute(select(Client).where(Client.id == invoice.client_id))).scalar_one_or_none()
    if client is None:
        raise ValidationException("Invoice has no valid client.")
    firm = (await session.execute(select(Tenant).where(Tenant.id == tenant.tenant_id))).scalar_one_or_none()

    pdf_bytes = render_invoice_pdf(
        invoice_number=invoice.number,
        firm_name=firm.name if firm else "NyayaAI Firm",
        firm_gstin=None,  # no GSTIN field on Tenant yet (plan C.11.1: optional)
        client_name=client.name,
        client_address=client.address,
        line_items=invoice.line_items,
        subtotal_paise=invoice.subtotal_paise,
        gst_rate=invoice.gst_rate,
        gst_paise=invoice.gst_paise,
        total_paise=invoice.total_paise,
        due_date=invoice.due_date.isoformat() if invoice.due_date else None,
        status=invoice.status.value if hasattr(invoice.status, "value") else invoice.status,
    )
    key = f"tenants/{tenant.tenant_id}/invoices/{invoice.id}.pdf"
    storage.put_object_bytes(key, pdf_bytes, content_type="application/pdf")
    invoice.s3_pdf_key = key

    if client.phone:
        link = await razorpay.create_payment_link(
            amount_paise=invoice.total_paise,
            description=f"Invoice {invoice.number}",
            customer_phone=client.phone,
        )
        invoice.razorpay_link = link["short_url"]

    invoice.status = InvoiceStatus.SENT
    await session.commit()
    await session.refresh(invoice)

    if client.user_id:
        await notify(
            session,
            tenant_id=tenant.tenant_id,
            user_id=client.user_id,
            # Contract B.8 has no distinct "invoice sent" push type; the
            # invoice deep link is the closest match (payment_received).
            type=NotificationType.PAYMENT_RECEIVED,
            title=f"Invoice {invoice.number}",
            body=f"You have a new invoice for Rs. {invoice.total_paise / 100:,.2f}.",
            data={"invoice_id": str(invoice.id)},
            channels={"push", "whatsapp", "sms"},
        )
    return invoice


async def get_pdf_url(invoice: Invoice) -> str:
    if not invoice.s3_pdf_key:
        raise ValidationException("Invoice PDF has not been generated yet; send the invoice first.")
    return storage.generate_presigned_download_url(invoice.s3_pdf_key, filename=f"{invoice.number}.pdf")


async def reconciliation_report(session: AsyncSession, tenant: TenantContext) -> list[dict]:
    """Plan C.11.5: paid vs pending vs overdue, by month (firm_admin)."""
    month = func.to_char(Invoice.created_at, "YYYY-MM")
    result = await session.execute(
        select(month, Invoice.status, func.count(), func.coalesce(func.sum(Invoice.total_paise), 0))
        .where(Invoice.tenant_id == tenant.tenant_id)
        .group_by(month, Invoice.status)
        .order_by(month.desc())
    )
    rows: dict[str, dict] = {}
    for m, status, count, total in result.all():
        key = status.value if hasattr(status, "value") else status
        bucket = rows.setdefault(m, {"month": m, "paid": 0, "pending": 0, "overdue": 0, "counts": {}})
        group = "paid" if key == "paid" else "overdue" if key == "overdue" else "pending"
        bucket[group] += int(total)
        bucket["counts"][key] = bucket["counts"].get(key, 0) + count
    return list(rows.values())
