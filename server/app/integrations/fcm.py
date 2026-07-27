"""Firebase Cloud Messaging (B.8).

Sends through the **HTTP v1 API**, which authenticates with a service-account JSON and
a short-lived OAuth token. The old `key=AAAA...` legacy endpoint was decommissioned in
2024 — if you find a tutorial using a server key, it is out of date.

Every push carries a `type` and a `deep_link` in its data payload, and the app routes on
those rather than on the notification body. B.8 also requires that an unrecognised type
is dropped silently rather than crashing an installed app that predates it.

**Data-only messages.** No `notification` block is sent. With a `notification` block,
Android displays the push itself when the app is backgrounded and the app never sees it —
which means no deep link routing, no channel choice, and no way to suppress a reminder
the user has already acted on. Data-only puts every message through
`NyayaMessagingService`, so behaviour is identical foreground and background.
"""

import logging
from typing import Any

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

FCM_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
FCM_ENDPOINT = "https://fcm.googleapis.com/v1/projects/{project}/messages:send"

# B.8 push types. The app has a matching enum that falls back to UNKNOWN.
HEARING_REMINDER = "hearing_reminder"
DAILY_DIGEST = "daily_digest"
CASE_UPDATE = "case_update"
AI_JOB_COMPLETE = "ai_job_complete"
PAYMENT_RECEIVED = "payment_received"
TASK_ASSIGNED = "task_assigned"


def is_live() -> bool:
    return bool(
        not settings.fake_mode
        and settings.firebase_project_id
        and settings.firebase_credentials_path
    )


async def _access_token() -> str | None:
    """Mints an OAuth token from the service-account key.

    google-auth is imported lazily so the server runs without it in FAKE_MODE — the
    demo must not require a Firebase account to exist.
    """
    try:
        from google.auth.transport.requests import Request  # type: ignore[import-untyped]
        from google.oauth2 import service_account  # type: ignore[import-untyped]
    except ImportError as exc:
        # Reports the real import error rather than assuming which package is missing.
        # google-auth can be installed and still fail here because its default transport
        # needs `requests`, which this codebase otherwise has no use for — a message
        # saying "google-auth is not installed" sends you looking in the wrong place.
        logger.error(
            "cannot send FCM: %s. Install with: pip install google-auth requests", exc
        )
        return None

    credentials = service_account.Credentials.from_service_account_file(
        settings.firebase_credentials_path, scopes=[FCM_SCOPE]
    )
    # Blocking, but it is cached for an hour by the library and only runs on a real send.
    credentials.refresh(Request())
    return credentials.token


async def send(
    token: str,
    push_type: str,
    title: str,
    body: str,
    deep_link: str | None = None,
    data: dict[str, str] | None = None,
) -> bool:
    """Sends one push. Returns False rather than raising — a failed notification must
    never fail the request that triggered it."""
    payload: dict[str, Any] = {
        "type": push_type,
        "title": title,
        "body": body,
        **({"deep_link": deep_link} if deep_link else {}),
        **(data or {}),
    }

    if not is_live():
        logger.info("FAKE PUSH -> %s: [%s] %s | %s", token[:12], push_type, title, deep_link)
        return True

    access_token = await _access_token()
    if access_token is None:
        return False

    message = {
        "message": {
            "token": token,
            # Data-only: see the module docstring.
            "data": {k: str(v) for k, v in payload.items()},
            "android": {
                "priority": "high" if push_type == HEARING_REMINDER else "normal",
            },
        }
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                FCM_ENDPOINT.format(project=settings.firebase_project_id),
                headers={"Authorization": f"Bearer {access_token}"},
                json=message,
            )
    except httpx.HTTPError as exc:
        logger.warning("FCM request failed: %s", exc)
        return False

    if response.status_code >= 400:
        # 404 UNREGISTERED means the app was uninstalled; the caller prunes the device.
        logger.warning("FCM rejected the message (%s): %s", response.status_code, response.text)
        return False
    return True


async def send_to_user(
    session,
    user_id,
    tenant_id,
    push_type: str,
    title: str,
    body: str,
    deep_link: str | None = None,
) -> int:
    """Fans out to every device the user has registered, and records the in-app
    notification row so the bell icon matches what was pushed.

    Returns the number of devices reached.
    """
    from sqlalchemy import select

    from app.models import Device, Notification

    session.add(
        Notification(
            tenant_id=tenant_id,
            user_id=user_id,
            type=push_type,
            title=title,
            body=body,
            deep_link=deep_link,
        )
    )

    devices = (
        await session.scalars(select(Device).where(Device.user_id == user_id))
    ).all()

    sent = 0
    for device in devices:
        if await send(device.fcm_token, push_type, title, body, deep_link):
            sent += 1
    return sent
