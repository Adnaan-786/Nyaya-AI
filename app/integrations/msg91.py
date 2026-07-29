"""
MSG91 SMS/OTP integration.

When settings.fake_mode is True (the default for local/dev/staging), no
network call is made -- the OTP is simply logged, so the full stack can
be run and tested offline (plan C.2: "All integrations have a
FAKE_MODE=true env switch that returns recorded responses").
"""

from app.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


async def send_otp_sms(phone: str, otp: str) -> None:
    settings = get_settings()

    if settings.fake_mode:
        logger.info("otp_sms_fake_send", phone=phone, otp=otp)
        return

    # Real MSG91 integration would go here, e.g.:
    #
    #   async with httpx.AsyncClient() as client:
    #       await client.post(
    #           "https://control.msg91.com/api/v5/otp",
    #           headers={"authkey": settings.msg91_auth_key},
    #           json={"mobile": phone, "otp": otp},
    #       )
    #
    # Left unimplemented until MSG91 credentials are provisioned (see
    # plan C.1: "Accounts/keys to obtain in Week 1").
    raise NotImplementedError(
        "Live MSG91 sending is not configured; set FAKE_MODE=true for now."
    )
