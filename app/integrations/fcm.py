"""
FCM push via the HTTP v1 API (httpx, no firebase-admin SDK dependency
needed -- consistent with this codebase's "plain HTTP call" pattern
for every other real integration). FAKE_MODE logs instead of sending,
same policy as MSG91/eCourts/LLM/etc.

Contract B.8: "All pushes are data messages (app builds the local
notification)." Every push carries {type, title, body, deep_link} plus
type-specific data fields.
"""

from app.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class FCMSendError(Exception):
    """Raised when a push fails to send for a reason other than an invalid/expired token."""


async def send_push(
    fcm_tokens: list[str],
    *,
    title: str,
    body: str,
    data: dict[str, str],
) -> list[str]:
    """
    Sends a data message to each token. Returns the list of tokens
    that were invalid/unregistered (the caller should prune these from
    the devices table -- plan C.5.5: "prune tokens >60 days stale" is
    the scheduled cleanup; a hard failure here is a more immediate signal).
    """
    settings = get_settings()

    if not fcm_tokens:
        return []

    if settings.fake_mode:
        logger.info(
            "fcm_fake_push",
            token_count=len(fcm_tokens),
            title=title,
            body=body,
            data=data,
        )
        return []

    if not settings.firebase_project_id or not settings.firebase_credentials_json:
        raise NotImplementedError(
            "Real FCM sending is not configured. Set FIREBASE_PROJECT_ID "
            "and FIREBASE_CREDENTIALS_JSON, or leave FAKE_MODE=true for now."
        )

    # Real sending needs a Google service-account OAuth2 token (JWT
    # bearer flow) exchanged for an access token, then HTTP v1 send
    # calls below. Left unimplemented until Firebase credentials are
    # provisioned -- same "don't build against guessed credentials"
    # policy as NAPIX/Document AI/Anthropic/Indian Kanoon elsewhere in
    # this codebase. The `google-auth` package (not yet a project
    # dependency) is the natural way to do the token exchange once
    # credentials exist.
    raise NotImplementedError(
        "Real FCM sending needs the Google service-account OAuth2 token "
        "exchange implemented once FIREBASE_CREDENTIALS_JSON points to a "
        "real service account. See the docstring above."
    )
