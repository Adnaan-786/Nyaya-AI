from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import AuthenticationException, ValidationException
from app.core.security import utcnow
from app.db.enums import InvoiceStatus, NotificationType, PaymentStatus
from app.db.rls import set_tenant
from app.db.session import AsyncSessionLocal
from app.db.tenant import TenantContext
from app.integrations import razorpay
from app.models.case_assignee import CaseAssignee
from app.models.invoice import Invoice
from app.models.payment import Payment
from app.models.tenant import Tenant
from app.models.user import User
from app.services.notification_dispatch_service import notify
from app.services.notification_templates import payment_received_copy

settings = get_settings()


async def create_payment_order(session: AsyncSession, tenant: TenantContext, invoice: Invoice) -> dict:
    """Contract B.10 step 2: POST /payments/order."""
    if invoice.status == InvoiceStatus.PAID:
        raise ValidationException("Invoice is already paid.")

    order = await razorpay.create_order(amount_paise=invoice.total_paise, receipt=invoice.number)
    session.add(
        Payment(
            tenant_id=tenant.tenant_id,
            invoice_id=invoice.id,
            razorpay_order_id=order["id"],
            amount_paise=invoice.total_paise,
            status=PaymentStatus.PENDING,
        )
    )
    await session.commit()
    return {
        "razorpay_order_id": order["id"],
        "amount_paise": invoice.total_paise,
        "key_id": settings.razorpay_key_id or "rzp_test_FAKE",
    }


async def verify_payment_client_side(
    session: AsyncSession, tenant: TenantContext, *, order_id: str, payment_id: str, signature: str
) -> Payment:
    """
    Contract B.10 step 4: checks the checkout signature and records the
    payment_id. The *authoritative* paid-flip is the webhook
    (handle_webhook) -- the app must treat the server's invoice status
    as truth, never its own SDK result.
    """
    if not settings.fake_mode and not razorpay.verify_payment_signature(
        order_id=order_id, payment_id=payment_id, signature=signature,
        key_secret=settings.razorpay_key_secret,
    ):
        raise AuthenticationException("Invalid payment signature.")

    payment = (
        await session.execute(
            select(Payment)
            .where(Payment.razorpay_order_id == order_id)
            .where(Payment.tenant_id == tenant.tenant_id)
        )
    ).scalar_one_or_none()
    if payment is None:
        raise ValidationException("No payment order found for this order_id.")

    payment.razorpay_payment_id = payment_id
    await session.commit()
    await session.refresh(payment)
    return payment


async def _find_tenant_for(model_column, value: str) -> UUID | None:
    """
    Razorpay webhooks carry no bearer token, but `payments` and
    `subscriptions` are RLS-protected, so the owning tenant has to be
    resolved before anything can be read. Low-volume (one per payment
    event), so checking each tenant's scope is an acceptable cost --
    the same system-context tenant loop the M5/M9 workers use.
    """
    async with AsyncSessionLocal() as session:
        tenant_ids = list((await session.execute(select(Tenant.id))).scalars().all())
    for tenant_id in tenant_ids:
        async with AsyncSessionLocal() as session:
            await set_tenant(session, str(tenant_id))
            found = await session.execute(select(model_column.class_.tenant_id).where(model_column == value))
            if found.scalar_one_or_none() is not None:
                return tenant_id
    return None


async def handle_webhook(payload: dict) -> Payment | None:
    """
    Plan C.11.4: idempotent by payment, marks the invoice paid, emits
    `payment_received`. Signature verification happens at the route
    (it needs the raw body). Returns None for replays / unrelated events.
    """
    if payload.get("event") not in ("payment.captured", "payment_link.paid"):
        return None

    entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
    payment_id, order_id = entity.get("id"), entity.get("order_id")
    if not payment_id or not order_id:
        return None

    tenant_id = await _find_tenant_for(Payment.razorpay_order_id, order_id)
    if tenant_id is None:
        return None

    async with AsyncSessionLocal() as session:
        await set_tenant(session, str(tenant_id))

        payment = (
            await session.execute(select(Payment).where(Payment.razorpay_order_id == order_id))
        ).scalar_one_or_none()
        if payment is None or payment.status == PaymentStatus.SUCCESS:
            return None  # idempotent replay

        payment.razorpay_payment_id = payment_id
        payment.status = PaymentStatus.SUCCESS
        payment.verified_at = utcnow()
        await session.commit()

        invoice = (
            await session.execute(select(Invoice).where(Invoice.id == payment.invoice_id))
        ).scalar_one_or_none()
        if invoice is not None and invoice.status != InvoiceStatus.PAID:
            invoice.status = InvoiceStatus.PAID
            await session.commit()
            await _notify_payment_received(session, invoice)
        return payment


async def _notify_payment_received(session: AsyncSession, invoice: Invoice) -> None:
    recipients: set[UUID] = set()
    if invoice.case_id:
        rows = await session.execute(select(CaseAssignee.user_id).where(CaseAssignee.case_id == invoice.case_id))
        recipients.update(r[0] for r in rows.all())
    if not recipients:
        rows = await session.execute(
            select(User.id).where(User.tenant_id == invoice.tenant_id).where(User.role == "firm_admin")
        )
        recipients.update(r[0] for r in rows.all())

    users = await session.execute(select(User).where(User.id.in_(recipients)))
    for user in users.scalars().all():
        title, body = payment_received_copy(amount_paise=invoice.total_paise, language=user.language)
        await notify(
            session,
            tenant_id=invoice.tenant_id,
            user_id=user.id,
            type=NotificationType.PAYMENT_RECEIVED,
            title=title,
            body=body,
            data={"invoice_id": str(invoice.id), "amount_paise": invoice.total_paise},
            channels={"push"},
        )
