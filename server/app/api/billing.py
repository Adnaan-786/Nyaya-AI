"""B.6 billing and B.10 payments."""

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Page, get_scoped_or_404, paginate
from app.core import envelope, security
from app.core.config import get_settings
from app.core.db import get_session, scoped
from app.core.india import today_in_india
from app.integrations import fcm, razorpay, sms, storage
from app.models import Case, Client, Expense, Invoice, Payment, TimeEntry
from app.schemas.billing import (
    ExpenseCreate,
    ExpenseOut,
    InvoiceCreate,
    InvoiceOut,
    InvoiceUpdate,
    PaymentOrderOut,
    PaymentOrderRequest,
    PaymentVerifyOut,
    PaymentVerifyRequest,
    TimeEntryCreate,
    TimeEntryOut,
    TimeEntryUpdate,
)
from app.services import invoicing

router = APIRouter(tags=["billing"])
settings = get_settings()

DEFAULT_PAYMENT_TERMS_DAYS = 15


def _to_out(invoice: Invoice) -> dict:
    payload = InvoiceOut.model_validate(invoice).model_dump(mode="json")
    payload["pdf_url"] = f"/v1/invoices/{invoice.id}/pdf" if invoice.pdf_key else None
    return payload


@router.get("/invoices")
async def list_invoices(
    status: str | None = Query(None, pattern="^(draft|sent|paid|overdue)$"),
    client_id: uuid.UUID | None = None,
    page: Page = Depends(),
    session: AsyncSession = Depends(get_session),
    principal: security.Principal = Depends(security.require_staff),
):
    statement = scoped(Invoice, principal.tenant_id)
    if status:
        statement = statement.where(Invoice.status == status)
    if client_id:
        statement = statement.where(Invoice.client_id == client_id)
    statement = statement.order_by(Invoice.created_at.desc())

    rows, meta = await paginate(session, statement, page)
    return envelope.ok([_to_out(r) for r in rows], meta)


@router.post("/invoices")
async def create_invoice(
    body: InvoiceCreate,
    session: AsyncSession = Depends(get_session),
    principal: security.Principal = Depends(security.require_staff),
):
    await get_scoped_or_404(session, Client, body.client_id, principal.tenant_id, "client")
    if body.case_id is not None:
        await get_scoped_or_404(session, Case, body.case_id, principal.tenant_id, "case")

    line_items = [item.model_dump() for item in body.line_items]
    imported: list[TimeEntry] = []

    if body.import_unbilled_time and body.case_id:
        # D.9 "Import unbilled time": pull billable, un-invoiced entries for the case
        # and mark them invoiced in the same transaction, so the same hour cannot be
        # billed twice by two invoices created minutes apart.
        imported = list(
            (
                await session.scalars(
                    scoped(TimeEntry, principal.tenant_id).where(
                        TimeEntry.case_id == body.case_id,
                        TimeEntry.billable.is_(True),
                        TimeEntry.invoiced_at.is_(None),
                        TimeEntry.rate_paise.isnot(None),
                    )
                )
            ).all()
        )
        for entry in imported:
            hours = max(1, round(entry.duration_seconds / 3600))
            line_items.append(
                {
                    "description": entry.description or "Professional services",
                    "quantity": hours,
                    "rate_paise": entry.rate_paise,
                    "amount_paise": hours * entry.rate_paise,
                }
            )

    if not line_items:
        raise envelope.validation("An invoice needs at least one line item.")

    subtotal, gst, total = invoicing.compute_totals(line_items, body.gst_rate, body.reverse_charge)
    today = today_in_india()

    invoice = Invoice(
        tenant_id=principal.tenant_id,
        client_id=body.client_id,
        case_id=body.case_id,
        number=await invoicing.next_invoice_number(session, principal.tenant_id, today),
        line_items=line_items,
        subtotal_paise=subtotal,
        gst_rate=body.gst_rate,
        gst_paise=gst,
        total_paise=total,
        status="draft",
        due_date=body.due_date or today + dt.timedelta(days=DEFAULT_PAYMENT_TERMS_DAYS),
    )
    session.add(invoice)

    now = dt.datetime.now(dt.UTC)
    for entry in imported:
        entry.invoiced_at = now

    await session.commit()
    await session.refresh(invoice)
    return envelope.ok(_to_out(invoice))


@router.get("/invoices/{invoice_id}")
async def get_invoice(
    invoice_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    principal: security.Principal = Depends(security.require_staff),
):
    invoice = await get_scoped_or_404(session, Invoice, invoice_id, principal.tenant_id, "invoice")
    return envelope.ok(_to_out(invoice))


@router.patch("/invoices/{invoice_id}")
async def update_invoice(
    invoice_id: uuid.UUID,
    body: InvoiceUpdate,
    session: AsyncSession = Depends(get_session),
    principal: security.Principal = Depends(security.require_staff),
):
    invoice = await get_scoped_or_404(session, Invoice, invoice_id, principal.tenant_id, "invoice")

    # A paid invoice is an accounting record, not a draft. Editing its amounts after
    # money has changed hands would silently desynchronise the books from reality.
    if invoice.status == "paid":
        raise envelope.validation("A paid invoice cannot be edited.")

    fields = body.model_dump(exclude_unset=True)
    if "line_items" in fields:
        invoice.line_items = [dict(item) for item in fields["line_items"]]
    if "gst_rate" in fields:
        invoice.gst_rate = fields["gst_rate"]
    if "due_date" in fields:
        invoice.due_date = fields["due_date"]
    if "status" in fields:
        invoice.status = fields["status"]

    reverse_charge = invoice.gst_paise == 0 and invoice.gst_rate > 0
    invoice.subtotal_paise, invoice.gst_paise, invoice.total_paise = invoicing.compute_totals(
        invoice.line_items, invoice.gst_rate, reverse_charge
    )

    await session.commit()
    await session.refresh(invoice)
    return envelope.ok(_to_out(invoice))


@router.post("/invoices/{invoice_id}/send")
async def send_invoice(
    invoice_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    principal: security.Principal = Depends(security.require_staff),
):
    """B.6: generates the PDF, creates a payment link, notifies the client."""
    invoice = await get_scoped_or_404(session, Invoice, invoice_id, principal.tenant_id, "invoice")
    client = await session.get(Client, invoice.client_id)

    pdf = await invoicing.render_pdf(session, invoice)
    key = storage.storage_key(str(principal.tenant_id), str(invoice.id), "invoice.pdf")
    await storage.put_object(key, pdf)
    invoice.pdf_key = key

    invoice.payment_link = await razorpay.create_payment_link(
        invoice.total_paise, f"Invoice {invoice.number}", client.phone if client else ""
    )
    invoice.status = "sent"
    await session.commit()
    await session.refresh(invoice)

    if client:
        await sms.send_text(
            client.phone,
            f"Invoice {invoice.number} for Rs {invoicing.format_paise(invoice.total_paise)} "
            f"is ready. Pay here: {invoice.payment_link}",
        )

    return envelope.ok(_to_out(invoice))


@router.get("/invoices/{invoice_id}/pdf")
async def invoice_pdf(
    invoice_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    principal: security.Principal = Depends(security.current_principal),
):
    """Readable by the firm and by the client the invoice belongs to — the client
    portal shows the same PDF (D.10)."""
    invoice = await session.get(Invoice, invoice_id)
    if invoice is None or invoice.tenant_id != principal.tenant_id:
        raise envelope.not_found("invoice")

    if principal.is_client:
        from app.models import User

        user = await session.get(User, principal.user_id)
        if user is None or user.client_id != invoice.client_id:
            raise envelope.not_found("invoice")

    if not invoice.pdf_key:
        pdf = await invoicing.render_pdf(session, invoice)
        invoice.pdf_key = storage.storage_key(
            str(invoice.tenant_id), str(invoice.id), "invoice.pdf"
        )
        await storage.put_object(invoice.pdf_key, pdf)
        await session.commit()
    else:
        pdf = await storage.get_object(invoice.pdf_key)

    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{invoice.number.replace("/", "-")}.pdf"'
        },
    )


@router.post("/payments/order")
async def create_payment_order(
    body: PaymentOrderRequest,
    session: AsyncSession = Depends(get_session),
    principal: security.Principal = Depends(security.current_principal),
):
    """B.10 step 2. Reachable by client-mode users — paying is the whole point."""
    invoice = await session.get(Invoice, body.invoice_id)
    if invoice is None or invoice.tenant_id != principal.tenant_id:
        raise envelope.not_found("invoice")

    if principal.is_client:
        from app.models import User

        user = await session.get(User, principal.user_id)
        if user is None or user.client_id != invoice.client_id:
            raise envelope.not_found("invoice")

    if invoice.status == "paid":
        raise envelope.duplicate("This invoice has already been paid.")

    order_id = await razorpay.create_order(invoice.total_paise, invoice.number)
    session.add(
        Payment(
            tenant_id=invoice.tenant_id,
            invoice_id=invoice.id,
            razorpay_order_id=order_id,
            amount_paise=invoice.total_paise,
            status="created",
        )
    )
    await session.commit()

    return envelope.ok(
        PaymentOrderOut(
            razorpay_order_id=order_id,
            amount_paise=invoice.total_paise,
            key_id=settings.razorpay_key_id or "rzp_test_placeholder",
        ).model_dump(mode="json")
    )


@router.post("/payments/verify")
async def verify_payment(
    body: PaymentVerifyRequest,
    session: AsyncSession = Depends(get_session),
    principal: security.Principal = Depends(security.current_principal),
):
    """B.10 step 4.

    The app reports what the Checkout SDK gave it; the server verifies the signature
    itself and decides. A forged or replayed callback must not mark anything paid —
    which is why the signature is recomputed here rather than trusted.
    """
    payment = (
        await session.scalars(select(Payment).where(Payment.razorpay_order_id == body.order_id))
    ).first()

    if payment is None or payment.tenant_id != principal.tenant_id:
        raise envelope.not_found("payment")

    if not razorpay.verify_checkout_signature(body.order_id, body.payment_id, body.signature):
        payment.status = "signature_failed"
        await session.commit()
        raise envelope.validation("This payment could not be verified.")

    payment.razorpay_payment_id = body.payment_id
    payment.verified_at = dt.datetime.now(dt.UTC)
    payment.status = "verified"

    invoice = await session.get(Invoice, payment.invoice_id)

    # B.10: verified signature AND webhook. In fake mode there is no webhook to
    # wait for, so settlement is applied here to keep the flow demonstrable — the
    # two-step logic itself is unchanged.
    if invoice is not None and not razorpay.is_live():
        payment.status = "captured"
        invoice.status = "paid"

    await session.commit()

    if invoice is not None and invoice.status == "paid":
        # Sent to the firm, not the payer: the lawyer is the one who wants to know
        # money landed. The client already saw their own payment succeed.
        await _notify_paid(session, invoice)
        await session.commit()

    return envelope.ok(
        PaymentVerifyOut(
            invoice_id=payment.invoice_id,
            invoice_status=invoice.status if invoice else "unknown",
            verified=True,
        ).model_dump(mode="json")
    )


@router.post("/payments/webhook")
async def razorpay_webhook(
    request: Request,
    session: AsyncSession = Depends(get_session),
    x_razorpay_signature: str = Header(default=""),
):
    """Razorpay -> us. Unauthenticated by nature, so the HMAC is the only gate."""
    raw = await request.body()
    if not razorpay.verify_webhook_signature(raw, x_razorpay_signature):
        raise envelope.ApiError(403, "WEBHOOK_SIGNATURE_INVALID", "Invalid signature.")

    import json

    event = json.loads(raw or b"{}")
    entity = event.get("payload", {}).get("payment", {}).get("entity", {})
    order_id = entity.get("order_id")
    if not order_id:
        return envelope.ok({"ok": True})

    payment = (
        await session.scalars(select(Payment).where(Payment.razorpay_order_id == order_id))
    ).first()
    if payment is None:
        return envelope.ok({"ok": True})

    if event.get("event") == "payment.captured":
        payment.status = "captured"
        payment.razorpay_payment_id = entity.get("id") or payment.razorpay_payment_id
        invoice = await session.get(Invoice, payment.invoice_id)
        if invoice is not None:
            invoice.status = "paid"
        await session.commit()

    return envelope.ok({"ok": True})


@router.get("/time-entries")
async def list_time_entries(
    case_id: uuid.UUID | None = None,
    unbilled_only: bool = False,
    page: Page = Depends(),
    session: AsyncSession = Depends(get_session),
    principal: security.Principal = Depends(security.require_staff),
):
    statement = scoped(TimeEntry, principal.tenant_id)
    if case_id:
        statement = statement.where(TimeEntry.case_id == case_id)
    if unbilled_only:
        statement = statement.where(TimeEntry.invoiced_at.is_(None))
    statement = statement.order_by(TimeEntry.started_at.desc())

    rows, meta = await paginate(session, statement, page)
    return envelope.ok([TimeEntryOut.model_validate(r).model_dump(mode="json") for r in rows], meta)


@router.post("/time-entries")
async def create_time_entry(
    body: TimeEntryCreate,
    session: AsyncSession = Depends(get_session),
    principal: security.Principal = Depends(security.require_staff),
):
    await get_scoped_or_404(session, Case, body.case_id, principal.tenant_id, "case")
    entry = TimeEntry(tenant_id=principal.tenant_id, user_id=principal.user_id, **body.model_dump())
    session.add(entry)
    await session.commit()
    await session.refresh(entry)
    return envelope.ok(TimeEntryOut.model_validate(entry).model_dump(mode="json"))


@router.patch("/time-entries/{time_entry_id}")
async def update_time_entry(
    time_entry_id: uuid.UUID,
    body: TimeEntryUpdate,
    session: AsyncSession = Depends(get_session),
    principal: security.Principal = Depends(security.require_staff),
):
    entry = await get_scoped_or_404(
        session, TimeEntry, time_entry_id, principal.tenant_id, "time_entry"
    )
    # Billed time is history now: an invoice already went out quoting this entry's
    # hours and rate, so editing it after the fact would silently desynchronise the
    # invoice from the record it was built from (same reasoning as the paid-invoice
    # guard in update_invoice above).
    if entry.invoiced_at is not None:
        raise envelope.validation(
            "This time entry has already been invoiced and cannot be changed."
        )

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(entry, field, value)

    await session.commit()
    await session.refresh(entry)
    return envelope.ok(TimeEntryOut.model_validate(entry).model_dump(mode="json"))


@router.delete("/time-entries/{time_entry_id}")
async def delete_time_entry(
    time_entry_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    principal: security.Principal = Depends(security.require_staff),
):
    entry = await get_scoped_or_404(
        session, TimeEntry, time_entry_id, principal.tenant_id, "time_entry"
    )
    if entry.invoiced_at is not None:
        raise envelope.validation(
            "This time entry has already been invoiced and cannot be changed."
        )

    await session.delete(entry)
    await session.commit()
    return envelope.ok({"ok": True})


@router.get("/expenses")
async def list_expenses(
    case_id: uuid.UUID | None = None,
    page: Page = Depends(),
    session: AsyncSession = Depends(get_session),
    principal: security.Principal = Depends(security.require_staff),
):
    statement = scoped(Expense, principal.tenant_id)
    if case_id:
        statement = statement.where(Expense.case_id == case_id)
    statement = statement.order_by(Expense.created_at.desc())

    rows, meta = await paginate(session, statement, page)
    return envelope.ok([ExpenseOut.model_validate(r).model_dump(mode="json") for r in rows], meta)


@router.post("/expenses")
async def create_expense(
    body: ExpenseCreate,
    session: AsyncSession = Depends(get_session),
    principal: security.Principal = Depends(security.require_staff),
):
    if body.case_id is not None:
        await get_scoped_or_404(session, Case, body.case_id, principal.tenant_id, "case")
    expense = Expense(tenant_id=principal.tenant_id, **body.model_dump())
    session.add(expense)
    await session.commit()
    await session.refresh(expense)
    return envelope.ok(ExpenseOut.model_validate(expense).model_dump(mode="json"))


async def _notify_paid(session: AsyncSession, invoice: Invoice) -> None:
    """B.8 payment_received, fanned out to every staff member of the firm."""
    from app.models import User

    staff = (
        await session.scalars(
            select(User).where(User.tenant_id == invoice.tenant_id, User.role != "client")
        )
    ).all()

    for member in staff:
        await fcm.send_to_user(
            session,
            user_id=member.id,
            tenant_id=invoice.tenant_id,
            push_type=fcm.PAYMENT_RECEIVED,
            title="Payment received",
            body=(
                f"Invoice {invoice.number} paid — "
                f"Rs {invoicing.format_paise(invoice.total_paise)}"
            ),
            deep_link=f"nyayaai://invoice/{invoice.id}",
        )
