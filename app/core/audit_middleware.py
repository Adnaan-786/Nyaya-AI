"""
Audit middleware (plan C.6 / C.12.1): every successful, authenticated
mutating request writes an `audit_logs` row -- who (actor), what
(`METHOD route-template`), and which resource.

Conventions
  * action       "POST /cases/{case_id}/hearings" (the route template,
                 so ids never leak into the action string)
  * entity_type  first path segment after the API prefix ("cases")
  * entity_id    the last UUID path parameter if there is one, otherwise
                 the `data.id` of the JSON response (i.e. the created
                 resource); NULL if neither exists

Failure policy: the row is written *after* the response is produced, in
its own transaction. If that write fails the request is NOT failed (the
mutation has already committed) -- the error is logged and sent to
Sentry. The residual risk is a process crash between the mutation's
commit and the audit write; closing that gap needs audit writes inside
the request's own transaction, which is a larger change (see README).
"""

import json
from typing import Any
from uuid import UUID

import sentry_sdk
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import get_settings
from app.core.logging import get_logger
from app.core.security import decode_access_token

logger = get_logger(__name__)

MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

# Not worth (or not able to be) audited: pre-login flows have no tenant,
# the payment webhook is unauthenticated, and device/read-receipt calls
# are high-volume bookkeeping on the caller's own data.
SKIP_PREFIXES = ("/auth/", "/payments/webhook", "/notifications/read", "/devices")
MAX_BODY_BYTES_TO_INSPECT = 1_000_000


def _is_uuid(value: Any) -> bool:
    try:
        UUID(str(value))
        return True
    except (ValueError, AttributeError, TypeError):
        return False


def build_audit_entry(
    *,
    method: str,
    path: str,
    route_template: str | None,
    path_params: dict[str, Any],
    status_code: int,
    claims: dict | None,
    response_json: Any,
    api_prefix: str,
    ip: str | None,
    user_agent: str | None,
) -> dict | None:
    """Pure function: the audit row for this request, or None if it shouldn't be audited."""
    if method not in MUTATING_METHODS or status_code >= 400 or not claims:
        return None

    relative = path[len(api_prefix):] if path.startswith(api_prefix) else path
    if relative.startswith(SKIP_PREFIXES):
        return None

    # Always the prefix-free template ("POST /cases/{case_id}/hearings"),
    # whether the router reports it with or without the mount prefix.
    template = route_template or path
    if template.startswith(api_prefix):
        template = template[len(api_prefix):]
    segments = [seg for seg in template.split("/") if seg]
    entity_type = segments[0] if segments else "unknown"

    uuid_params = [str(v) for v in path_params.values() if _is_uuid(v)]
    entity_id = uuid_params[-1] if uuid_params else None
    if entity_id is None and isinstance(response_json, dict):
        data = response_json.get("data")
        if isinstance(data, dict) and _is_uuid(data.get("id")):
            entity_id = str(data["id"])

    return {
        "tenant_id": claims["tenant_id"],
        "actor_id": claims["sub"],
        "action": f"{method} {template}",
        "entity_type": entity_type,
        "entity_id": entity_id,
        "ip": ip,
        "user_agent": (user_agent or "")[:500] or None,
    }


def _claims_from(request: Request) -> dict | None:
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        return None
    try:
        return decode_access_token(header[7:].strip())
    except Exception:  # noqa: BLE001 - invalid/expired token: nothing to attribute
        return None


async def write_audit_row(entry: dict) -> None:
    from app.db.rls import set_tenant
    from app.db.session import AsyncSessionLocal
    from app.models.audit_log import AuditLog

    async with AsyncSessionLocal() as session:
        await set_tenant(session, entry["tenant_id"])
        session.add(
            AuditLog(
                tenant_id=UUID(entry["tenant_id"]),
                actor_id=UUID(entry["actor_id"]),
                action=entry["action"],
                entity_type=entry["entity_type"],
                entity_id=entry["entity_id"],
                ip=entry["ip"],
                user_agent=entry["user_agent"],
            )
        )
        await session.commit()


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        if request.method not in MUTATING_METHODS or response.status_code >= 400:
            return response

        claims = _claims_from(request)
        if not claims:
            return response

        # Read the body so the created resource's id can be recorded,
        # then hand back an equivalent response.
        body = b""
        async for chunk in response.body_iterator:
            body += chunk
        rebuilt = Response(
            content=body,
            status_code=response.status_code,
            headers={k: v for k, v in response.headers.items() if k.lower() != "content-length"},
            media_type=response.media_type,
        )

        response_json = None
        if body and len(body) <= MAX_BODY_BYTES_TO_INSPECT and "json" in (response.headers.get("content-type") or ""):
            try:
                response_json = json.loads(body)
            except ValueError:
                response_json = None

        route = request.scope.get("route")
        entry = build_audit_entry(
            method=request.method,
            path=request.url.path,
            route_template=getattr(route, "path", None),
            path_params=request.scope.get("path_params", {}),
            status_code=response.status_code,
            claims=claims,
            response_json=response_json,
            api_prefix=get_settings().api_prefix,
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        if entry is not None:
            try:
                await write_audit_row(entry)
            except Exception as exc:  # noqa: BLE001 - never fail a request that already succeeded
                sentry_sdk.capture_exception(exc)
                logger.error("audit_write_failed", action=entry["action"], error=str(exc))

        return rebuilt
