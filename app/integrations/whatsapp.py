"""
Gupshup WhatsApp Business API integration. FAKE_MODE logs instead of
sending, same policy as every other integration.

Plan C.10 point 3: "WhatsApp templates require Meta approval -- submit
in Week 3 (EN + HI variants)." Meta template approval is a manual,
non-code step the team must do in the Gupshup/Meta Business dashboard;
this module assumes approved template names are configured once that
happens (see WHATSAPP_TEMPLATE_NAMES below).
"""

from app.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Maps our notification types to the (not-yet-existing) Meta-approved
# WhatsApp template name. Fill in once templates are approved -- the
# dispatcher only calls send_whatsapp_template for types present here.
WHATSAPP_TEMPLATE_NAMES: dict[str, str] = {
    "hearing_reminder": "hearing_reminder_v1",
    "daily_digest": "daily_digest_v1",
}


class WhatsAppSendError(Exception):
    """Raised when a WhatsApp template message fails to send."""


async def send_whatsapp_template(
    phone: str, *, notification_type: str, params: list[str]
) -> bool:
    """
    Returns True if the message was (or would be, in fake mode) sent.
    False means the caller should fall back to SMS (plan C.10: "SMS
    fallback if WA fails/unsubscribed").
    """
    settings = get_settings()

    template_name = WHATSAPP_TEMPLATE_NAMES.get(notification_type)
    if template_name is None:
        return False

    if settings.fake_mode:
        logger.info(
            "whatsapp_fake_send",
            phone=phone,
            template=template_name,
            params=params,
        )
        return True

    if not settings.gupshup_api_key:
        raise NotImplementedError(
            "Real Gupshup WhatsApp sending is not configured. Set "
            "GUPSHUP_API_KEY and GUPSHUP_SOURCE_NUMBER, or leave "
            "FAKE_MODE=true for now."
        )

    import httpx

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            "https://api.gupshup.io/wa/api/v1/template/msg",
            headers={"apikey": settings.gupshup_api_key},
            data={
                "source": settings.gupshup_source_number,
                "destination": phone,
                "template": template_name,
                "params": params,
            },
        )

    if response.status_code >= 400:
        logger.warning(
            "whatsapp_send_failed", status=response.status_code, body=response.text[:300]
        )
        return False

    return True
