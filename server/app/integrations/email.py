"""Transactional email — Brevo HTTP API (preferred) or SMTP (fallback).

**Two delivery paths, one interface.**

1. Brevo HTTP API (``BREVO_API_KEY``) — a single POST over port 443. Required on
   hosts like Render that block outbound SMTP ports (25/465/587).
2. SMTP (``SMTP_HOST`` + friends) — the stdlib ``smtplib``, provider-agnostic.
   Works on any host that allows outbound SMTP.

If both are configured the HTTP path wins: it is faster (no TLS handshake, no
multi-step SMTP conversation) and immune to port-blocking.

Unlike SMS, email needs no DLT registration, no template pre-approval, and no
registered business entity — which is the entire reason the login channel moved
here.
"""

import asyncio
import logging
import smtplib
import ssl
from email.message import EmailMessage

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

SMTP_TIMEOUT_SECONDS = 15
BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"


class EmailDeliveryError(Exception):
    """A message the caller's request depends on could not be handed to the relay."""


def _has_brevo() -> bool:
    return bool(not settings.fake_mode and settings.brevo_api_key and settings.smtp_from)


def _has_smtp() -> bool:
    return bool(
        not settings.fake_mode
        and settings.smtp_host
        and settings.smtp_username
        and settings.smtp_password
        and settings.smtp_from
    )


def is_live() -> bool:
    """True only when a real email can actually be delivered."""
    return _has_brevo() or _has_smtp()


# ---------------------------------------------------------------------------
# Brevo HTTP path
# ---------------------------------------------------------------------------

async def _send_brevo(to: str, subject: str, body: str) -> None:
    payload = {
        "sender": {"email": settings.smtp_from, "name": "NyayaAI"},
        "to": [{"email": to}],
        "subject": subject,
        "textContent": body,
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            BREVO_API_URL,
            json=payload,
            headers={
                "api-key": settings.brevo_api_key,
                "Content-Type": "application/json",
            },
        )
    if resp.status_code >= 400:
        detail = resp.text[:200]
        logger.error("Brevo API %s for %s: %s", resp.status_code, to, detail)
        raise EmailDeliveryError(f"Brevo {resp.status_code}: {detail}")


# ---------------------------------------------------------------------------
# SMTP path (fallback for hosts that allow outbound SMTP)
# ---------------------------------------------------------------------------

def _build(to: str, subject: str, body: str) -> EmailMessage:
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.smtp_from
    message["To"] = to
    message.set_content(body)
    return message


def _send_blocking(message: EmailMessage) -> None:
    context = ssl.create_default_context()
    if settings.smtp_port == 465:
        with smtplib.SMTP_SSL(
            settings.smtp_host, settings.smtp_port, timeout=SMTP_TIMEOUT_SECONDS, context=context
        ) as server:
            server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(message)
        return

    with smtplib.SMTP(
        settings.smtp_host, settings.smtp_port, timeout=SMTP_TIMEOUT_SECONDS
    ) as server:
        server.starttls(context=context)
        server.login(settings.smtp_username, settings.smtp_password)
        server.send_message(message)


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

async def send(to: str, subject: str, body: str) -> None:
    """Sends one email, raising [EmailDeliveryError] if the relay would not take it."""
    if not is_live():
        logger.info("FAKE EMAIL -> %s | %s | %s", to, subject, body)
        return

    if _has_brevo():
        try:
            await _send_brevo(to, subject, body)
        except httpx.HTTPError as exc:
            logger.error("Brevo HTTP error for %s: %s", to, exc)
            raise EmailDeliveryError(str(exc)) from exc
        return

    try:
        await asyncio.to_thread(_send_blocking, _build(to, subject, body))
    except (smtplib.SMTPException, OSError) as exc:
        logger.error("SMTP refused a message to %s: %s", to, exc)
        raise EmailDeliveryError(str(exc)) from exc


OTP_SUBJECT = "Your NyayaAI verification code"


async def send_otp(to: str, code: str) -> None:
    await send(
        to,
        OTP_SUBJECT,
        f"Your NyayaAI verification code is {code}.\n\n"
        f"It is valid for 5 minutes. If you did not request it, you can ignore this email.",
    )
