"""SMS delivery (MSG91), with the FAKE_MODE switch every integration honours.

C.2 requires the whole stack to run offline. For SMS this is not just convenience:
sending transactional SMS in India requires a DLT-registered template, and until that
registration clears, real delivery is impossible regardless of account status. Fake
mode keeps every OTP flow demonstrable in the meantime.
"""

import logging

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# In fake mode every OTP is this, so the demo and the automated tests are deterministic.
FAKE_OTP = "123456"


async def send_otp(phone: str, code: str) -> None:
    if settings.fake_mode or not settings.msg91_auth_key:
        logger.info("FAKE SMS -> %s: your NyayaAI code is %s", phone, code)
        return

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            "https://control.msg91.com/api/v5/otp",
            params={
                "template_id": settings.msg91_template_id,
                "mobile": phone.lstrip("+"),
                "otp": code,
            },
            headers={"authkey": settings.msg91_auth_key},
        )
        response.raise_for_status()


async def send_text(phone: str, message: str) -> None:
    """Used for client portal invites and payment links (B.4 roles, B.10)."""
    if settings.fake_mode or not settings.msg91_auth_key:
        logger.info("FAKE SMS -> %s: %s", phone, message)
        return

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            "https://control.msg91.com/api/v5/flow/",
            json={"mobiles": phone.lstrip("+"), "message": message},
            headers={"authkey": settings.msg91_auth_key},
        )
        response.raise_for_status()
