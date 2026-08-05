"""Transactional email over SMTP, with the FAKE_MODE switch every integration honours.

**Why SMTP and not a vendor API.** Every other outbound integration here speaks HTTP
because that is all its provider offers. Email has an actual protocol, and using it
means the free tier this runs on (Brevo, Gmail, SendGrid, Mailgun, Resend — all of them
expose SMTP) is a matter of environment variables rather than a code change. That
matters more than usual here: this is the login channel, and the free tier it depends
on is the sort of thing that gets repriced.

**Why `smtplib` and not `aiosmtplib`.** It is in the standard library, so it cannot go
missing from `requirements.txt` — a failure this project has already shipped twice
(`fpdf2`, `boto3`). It is blocking, so the send runs in a worker thread; at OTP volume
that is cheaper than owning another dependency on the critical path of signing in.

Unlike SMS, this needs no DLT registration, no template pre-approval, and no registered
business entity — which is the entire reason the login channel moved here.
"""

import asyncio
import logging
import smtplib
import ssl
from email.message import EmailMessage

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

SMTP_TIMEOUT_SECONDS = 15


class EmailDeliveryError(Exception):
    """A message the caller's request depends on could not be handed to the relay."""


def is_live() -> bool:
    """True only when a real email can actually be delivered.

    Asks about *this* integration's own credentials rather than the global FAKE_MODE
    flag, so turning on one live integration cannot silently change another's
    behaviour.
    """
    return bool(
        not settings.fake_mode
        and settings.smtp_host
        and settings.smtp_username
        and settings.smtp_password
        and settings.smtp_from
    )


def _build(to: str, subject: str, body: str) -> EmailMessage:
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.smtp_from
    message["To"] = to
    message.set_content(body)
    return message


def _send_blocking(message: EmailMessage) -> None:
    """Runs on a worker thread — see the module docstring.

    Port 465 is implicit TLS (SMTP_SSL); everything else is assumed to be STARTTLS,
    which is what 587 means and what every provider below defaults to. Getting this
    backwards is the classic "hangs then times out" SMTP misconfiguration, so it is
    decided from the port rather than left as one more thing to set correctly.
    """
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


async def send(to: str, subject: str, body: str) -> None:
    """Sends one email, raising [EmailDeliveryError] if the relay would not take it.

    Raises rather than returning a bool because the only caller so far is the OTP
    request, where this message *is* the request's purpose — reporting success on a
    failed send would leave someone waiting on a code that is never coming.
    """
    if not is_live():
        logger.info("FAKE EMAIL -> %s | %s | %s", to, subject, body)
        return

    try:
        await asyncio.to_thread(_send_blocking, _build(to, subject, body))
    except (smtplib.SMTPException, OSError) as exc:
        # OSError covers the connection-level failures (DNS, refused, timeout) that
        # smtplib lets through unwrapped.
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
