"""
Razorpay integration.

Signature verification (checkout callback and webhook) is real
HMAC-SHA256 -- it only needs the shared secret, so it is implemented
for real. Order/payment-link/subscription *creation* calls the real
Razorpay API behind RAZORPAY_KEY_ID/SECRET; FAKE_MODE returns
realistic fake IDs so the whole flow runs offline, same policy as
every other integration here.
"""

import hashlib
import hmac
import uuid

from app.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class RazorpayError(Exception):
    """Raised when a Razorpay API call fails."""


def verify_payment_signature(*, order_id: str, payment_id: str, signature: str, key_secret: str) -> bool:
    """Contract B.10 step 4: HMAC-SHA256(order_id|payment_id, key_secret)."""
    payload = f"{order_id}|{payment_id}".encode()
    expected = hmac.new(key_secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def verify_webhook_signature(*, body: bytes, signature: str, webhook_secret: str) -> bool:
    """Plan C.11.4: verifies `X-Razorpay-Signature` = HMAC-SHA256(raw body, webhook_secret)."""
    expected = hmac.new(webhook_secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def _require_keys(what: str) -> tuple[str, str]:
    settings = get_settings()
    if not settings.razorpay_key_id or not settings.razorpay_key_secret:
        raise NotImplementedError(
            f"Real Razorpay {what} is not configured. Set RAZORPAY_KEY_ID and "
            "RAZORPAY_KEY_SECRET, or leave FAKE_MODE=true for now."
        )
    return settings.razorpay_key_id, settings.razorpay_key_secret


async def _post(path: str, json: dict) -> dict:
    import httpx

    key_id, key_secret = _require_keys(path)
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            f"https://api.razorpay.com/v1/{path}", auth=(key_id, key_secret), json=json
        )
    if response.status_code >= 400:
        raise RazorpayError(f"Razorpay {path} failed: {response.text[:300]}")
    return response.json()


async def create_order(*, amount_paise: int, receipt: str) -> dict:
    """Returns {"id", "amount", "currency"} (contract B.10: POST /payments/order)."""
    if get_settings().fake_mode:
        order_id = f"order_FAKE{uuid.uuid4().hex[:14]}"
        logger.info("razorpay_fake_order", order_id=order_id, amount_paise=amount_paise)
        return {"id": order_id, "amount": amount_paise, "currency": "INR"}
    return await _post("orders", {"amount": amount_paise, "currency": "INR", "receipt": receipt})


async def create_payment_link(*, amount_paise: int, description: str, customer_phone: str) -> dict:
    """Returns {"id", "short_url"} (plan C.11.3)."""
    if get_settings().fake_mode:
        link_id = f"plink_FAKE{uuid.uuid4().hex[:14]}"
        return {"id": link_id, "short_url": f"https://fixtures.local/razorpay/pay/{link_id}"}
    return await _post(
        "payment_links",
        {
            "amount": amount_paise,
            "currency": "INR",
            "description": description,
            "customer": {"contact": customer_phone},
            "notify": {"sms": True, "whatsapp": True},
        },
    )


async def create_subscription(*, plan_razorpay_id: str) -> dict:
    """Returns {"id", "short_url"} for a Subscription (UPI Autopay / card mandate), contract B.14."""
    if get_settings().fake_mode:
        sub_id = f"sub_FAKE{uuid.uuid4().hex[:14]}"
        return {"id": sub_id, "short_url": f"https://fixtures.local/razorpay/sub/{sub_id}"}
    return await _post(
        "subscriptions", {"plan_id": plan_razorpay_id, "customer_notify": 1, "total_count": 120}
    )
