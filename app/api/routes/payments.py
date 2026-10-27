from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.dependencies import AuthContext, get_tenant_scoped_db
from app.core.exceptions import AuthenticationException
from app.core.rbac import require
from app.core.responses import ApiResponse
from app.integrations import razorpay
from app.schemas.payment import PaymentOrderIn, PaymentOrderOut, PaymentVerifyIn
from app.services import invoice_service, payment_service, subscription_service

router = APIRouter(prefix="/payments", tags=["Payments"])


@router.post("/order", response_model=ApiResponse[PaymentOrderOut])
async def create_payment_order(
    payload: PaymentOrderIn,
    auth: AuthContext = Depends(require("billing.read")),  # clients pay their own invoices too
    session: AsyncSession = Depends(get_tenant_scoped_db),
) -> ApiResponse[PaymentOrderOut]:
    tenant = auth.as_tenant_context()
    invoice = await invoice_service.get_invoice_or_404(session, tenant, payload.invoice_id)
    order = await payment_service.create_payment_order(session, tenant, invoice)
    return ApiResponse(success=True, data=PaymentOrderOut(**order))


@router.post("/verify", response_model=ApiResponse[dict])
async def verify_payment(
    payload: PaymentVerifyIn,
    auth: AuthContext = Depends(require("billing.read")),
    session: AsyncSession = Depends(get_tenant_scoped_db),
) -> ApiResponse[dict]:
    await payment_service.verify_payment_client_side(
        session, auth.as_tenant_context(),
        order_id=payload.order_id, payment_id=payload.payment_id, signature=payload.signature,
    )
    # Only confirms the signature checked out; the invoice flips to
    # paid via the webhook (contract B.10: server status is truth).
    return ApiResponse(success=True, data={"signature_verified": True})


@router.post("/webhook", response_model=ApiResponse[dict])
async def razorpay_webhook(
    request: Request, x_razorpay_signature: str | None = Header(default=None)
) -> ApiResponse[dict]:
    """Unauthenticated: Razorpay calls this directly, so authenticity is the signature alone."""
    settings = get_settings()
    raw_body = await request.body()

    if not settings.fake_mode and (
        not x_razorpay_signature
        or not razorpay.verify_webhook_signature(
            body=raw_body, signature=x_razorpay_signature, webhook_secret=settings.razorpay_webhook_secret
        )
    ):
        raise AuthenticationException("Invalid webhook signature.")

    payload = await request.json()
    if payload.get("event") == "subscription.activated":
        sub_id = payload.get("payload", {}).get("subscription", {}).get("entity", {}).get("id")
        if sub_id:
            await subscription_service.activate_subscription(sub_id)
    else:
        await payment_service.handle_webhook(payload)

    return ApiResponse(success=True, data={"received": True})
