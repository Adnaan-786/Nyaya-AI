"""Razorpay orders, signature verification and webhooks (B.10).

The security property that matters: **an invoice is marked paid only by the server**,
after verifying Razorpay's HMAC signature. The app is never trusted — it reports what
the Checkout SDK told it, and the server independently decides. B.10 is explicit that
the app treats the invoice status from the server as truth, never its own SDK result.

Signature schemes (both HMAC-SHA256, different keys and payloads):
  * Checkout callback — `order_id|payment_id`, keyed with the API secret.
  * Webhook          — the raw request body, keyed with the webhook secret.
"""

import hashlib
import hmac
import logging
import uuid

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

API_BASE = "https://api.razorpay.com/v1"


def is_live() -> bool:
    return bool(
        not settings.fake_mode and settings.razorpay_key_id and settings.razorpay_key_secret
    )


async def create_order(amount_paise: int, receipt: str) -> str:
    """Razorpay's own unit is paise, which is why the whole system uses it."""
    if not is_live():
        return f"order_fake{uuid.uuid4().hex[:14]}"

    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(
            f"{API_BASE}/orders",
            auth=(settings.razorpay_key_id, settings.razorpay_key_secret),
            json={"amount": amount_paise, "currency": "INR", "receipt": receipt},
        )
        response.raise_for_status()
        return response.json()["id"]


def verify_checkout_signature(order_id: str, payment_id: str, signature: str) -> bool:
    """B.10 step 4. `compare_digest` because this gate is worth money."""
    if not is_live():
        # Fake mode accepts a deterministic signature so the payment flow is
        # demonstrable end to end, and rejects anything else — the verification
        # branch is still exercised rather than stubbed to always-true.
        return signature == fake_signature(order_id, payment_id)

    expected = hmac.new(
        settings.razorpay_key_secret.encode(),
        f"{order_id}|{payment_id}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def fake_signature(order_id: str, payment_id: str) -> str:
    """The signature the app would receive from Checkout in test mode."""
    return hmac.new(
        b"fake-razorpay-secret", f"{order_id}|{payment_id}".encode(), hashlib.sha256
    ).hexdigest()


def verify_webhook_signature(raw_body: bytes, signature: str) -> bool:
    """Webhooks are unauthenticated HTTP — the signature is the only thing standing
    between a stranger and marking every invoice paid."""
    secret = settings.razorpay_webhook_secret
    if not secret:
        logger.warning("razorpay webhook received but no webhook secret is configured")
        return False

    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


async def create_payment_link(amount_paise: int, description: str, phone: str) -> str:
    """B.10 step 1: the client gets a link by SMS without needing the app."""
    if not is_live():
        return f"https://rzp.io/i/fake{uuid.uuid4().hex[:10]}"

    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(
            f"{API_BASE}/payment_links",
            auth=(settings.razorpay_key_id, settings.razorpay_key_secret),
            json={
                "amount": amount_paise,
                "currency": "INR",
                "description": description[:200],
                "customer": {"contact": phone},
                "notify": {"sms": True},
            },
        )
        response.raise_for_status()
        return response.json()["short_url"]
