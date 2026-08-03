"""SMS delivery (MSG91), with the FAKE_MODE switch every integration honours.

C.2 requires the whole stack to run offline. For SMS this is not just convenience:
sending transactional SMS in India requires a DLT-registered template, and until that
registration clears, real delivery is impossible regardless of account status. Fake
mode keeps every OTP flow demonstrable in the meantime.

**Every message is a registered template, not a string.** Under TRAI's DLT regime an
SMS whose body does not match a pre-approved template is *rejected by the operator*,
not delivered with a warning — MSG91 answers with error 211, "No DLT Template ID or
Invalid Template ID". So this module exposes one function per message the product
sends, each bound to its own template ID, rather than a `send_text(phone, anything)`
that reads fine locally and can never work in production. The exact bodies to register
are in the docstring of each function; they must match character-for-character, and
any URL inside one has to be whitelisted on the DLT portal separately.

**MSG91 reports failures with HTTP 200.** A rejected send comes back as
`{"type": "error", "message": "..."}` with a 200 status, so `raise_for_status()` alone
silently treats a delivery failure as success. Both are checked here, and the response
body is logged on failure — the same lesson the Groq integration learned the hard way,
where the status code alone never said *why*.
"""

import logging
from typing import Any

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# In fake mode every OTP is this, so the demo and the automated tests are deterministic.
FAKE_OTP = "123456"

OTP_URL = "https://control.msg91.com/api/v5/otp"
FLOW_URL = "https://control.msg91.com/api/v5/flow/"

REQUEST_TIMEOUT_SECONDS = 10


class SmsDeliveryError(Exception):
    """A message that the caller's request depends on could not be delivered."""


def is_live() -> bool:
    """True only when a real SMS can actually be delivered.

    Every integration answers this question about its *own* credentials rather than
    about the global FAKE_MODE flag, so enabling one live integration cannot silently
    change the behaviour of another.
    """
    return bool(not settings.fake_mode and settings.msg91_auth_key)


def _check(response: httpx.Response, what: str) -> None:
    """Raises unless MSG91 both returned 2xx *and* said the send succeeded.

    See the module docstring: a 200 here does not mean delivered.
    """
    if response.is_error:
        logger.error("MSG91 rejected %s (HTTP %s): %s", what, response.status_code, response.text)
        raise SmsDeliveryError(f"MSG91 returned HTTP {response.status_code}")

    try:
        body = response.json()
    except ValueError:
        logger.error("MSG91 sent a non-JSON reply for %s: %s", what, response.text)
        raise SmsDeliveryError("MSG91 sent an unreadable response") from None

    if isinstance(body, dict) and body.get("type") == "error":
        logger.error("MSG91 refused %s: %s", what, body.get("message"))
        raise SmsDeliveryError(str(body.get("message") or "MSG91 refused the message"))


async def _send_template(
    template_id: str | None,
    phone: str,
    variables: dict[str, str],
    what: str,
) -> None:
    """One flow-API send. `variables` keys must match the variable names in the
    DLT-approved template exactly."""
    if not template_id:
        # Distinct from "no auth key": the account is live but this particular template
        # was never registered, so only this one message type is undeliverable.
        logger.error("cannot send %s: its MSG91 template ID is not configured", what)
        raise SmsDeliveryError(f"No MSG91 template configured for {what}")

    recipient: dict[str, Any] = {"mobiles": phone.lstrip("+"), **variables}
    payload: dict[str, Any] = {"template_id": template_id, "recipients": [recipient]}
    if settings.msg91_sender_id:
        payload["sender"] = settings.msg91_sender_id

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        response = await client.post(
            FLOW_URL,
            json=payload,
            headers={"authkey": settings.msg91_auth_key, "Content-Type": "application/json"},
        )
    _check(response, what)


async def send_otp(phone: str, code: str) -> None:
    """Register as: `{#var#} is your NyayaAI verification code. It is valid for 5 minutes.`

    Raises [SmsDeliveryError] rather than swallowing a failure, because unlike every
    other message here this SMS *is* the request's purpose — a caller that reported
    success on a failed send would leave the user waiting on a code that never comes.
    """
    if not is_live():
        logger.info("FAKE SMS -> %s: your NyayaAI code is %s", phone, code)
        return

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        response = await client.post(
            OTP_URL,
            params={
                "template_id": settings.msg91_template_id,
                "mobile": phone.lstrip("+"),
                "otp": code,
            },
            headers={"authkey": settings.msg91_auth_key},
        )
    _check(response, "an OTP")


async def send_client_invite(phone: str, client_name: str, reference: str) -> bool:
    """Client portal invite (B.4 roles).

    Register as: `{#var#}, you can now follow your case with NyayaAI. Sign in with this
    number. Reference: {#var#}` with variables `name` and `ref`.
    """
    message = (
        f"{client_name}, you can now follow your case with NyayaAI. "
        f"Sign in with this number. Reference: {reference}"
    )
    return await _fire_and_forget(
        settings.msg91_template_client_invite,
        phone,
        {"name": client_name, "ref": reference},
        "a client invite",
        message,
    )


async def send_invoice_link(
    phone: str, invoice_number: str, amount: str, payment_link: str
) -> bool:
    """Invoice payment link (B.10).

    Register as: `Invoice {#var#} for Rs {#var#} is ready. Pay here: {#var#}` with
    variables `number`, `amount` and `link`. The link's domain must also be whitelisted
    on the DLT portal, or the operator drops the message even with the template approved.
    """
    message = f"Invoice {invoice_number} for Rs {amount} is ready. Pay here: {payment_link}"
    return await _fire_and_forget(
        settings.msg91_template_invoice,
        phone,
        {"number": invoice_number, "amount": amount, "link": payment_link},
        "an invoice link",
        message,
    )


async def _fire_and_forget(
    template_id: str | None,
    phone: str,
    variables: dict[str, str],
    what: str,
    fake_preview: str,
) -> bool:
    """Sends, but reports failure as `False` instead of raising.

    These messages are side effects of work that has already committed — an invoice is
    raised, a client is invited — so a failed SMS must not fail the request that
    triggered it, exactly as in `fcm.py`. `fake_preview` is the human-readable body,
    used only for the FAKE_MODE log line so the demo still shows what would be sent.
    """
    if not is_live():
        logger.info("FAKE SMS -> %s: %s", phone, fake_preview)
        return True

    try:
        await _send_template(template_id, phone, variables, what)
    except (SmsDeliveryError, httpx.HTTPError) as exc:
        logger.warning("could not send %s to %s: %s", what, phone, exc)
        return False
    return True
