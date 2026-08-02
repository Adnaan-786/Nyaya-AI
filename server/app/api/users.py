"""Team management: list the firm's staff, change a member's role, remove a member.

There is no create-member endpoint — team members arrive by signing in with OTP and
being onboarded (`/auth/onboard`) the same way a firm's first admin does; this router
only manages people already in the tenant.
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Page, get_scoped_or_404, paginate
from app.core import envelope, security
from app.core.db import get_session, scoped
from app.models import User
from app.schemas.users import UserOut, UserRoleUpdate

router = APIRouter(tags=["users"])


@router.get("/users")
async def list_users(
    page: Page = Depends(),
    session: AsyncSession = Depends(get_session),
    # Read-only team visibility: `clients.py`'s list endpoint is also require_staff
    # (not admin-only), so any staff member seeing their own team's roster follows
    # the same precedent — only the role-changing/removal writes below are admin-only.
    principal: security.Principal = Depends(security.require_staff),
):
    statement = (
        scoped(User, principal.tenant_id)
        .where(User.role != "client", User.is_active.is_(True))
        .order_by(User.name)
    )
    rows, meta = await paginate(session, statement, page)
    return envelope.ok([UserOut.model_validate(r).model_dump(mode="json") for r in rows], meta)


@router.patch("/users/{user_id}")
async def update_user_role(
    user_id: uuid.UUID,
    body: UserRoleUpdate,
    session: AsyncSession = Depends(get_session),
    principal: security.Principal = Depends(security.require_roles("firm_admin")),
):
    if user_id == principal.user_id:
        # A footgun with no legitimate use case, not a "last admin" business rule to
        # enforce with a count query — an admin changing their own role through this
        # endpoint is always a mistake (or self-lockout), so it is refused outright.
        raise envelope.validation("You cannot change your own role.")

    member = await get_scoped_or_404(session, User, user_id, principal.tenant_id, "user")
    if member.role == "client":
        # A client-role login is not a team member; this boundary mirrors
        # `invite_client`'s refusal to demote a staff member the other direction.
        raise envelope.not_found("user")

    member.role = body.role
    await session.commit()
    await session.refresh(member)
    return envelope.ok(UserOut.model_validate(member).model_dump(mode="json"))


@router.delete("/users/{user_id}")
async def remove_user(
    user_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    principal: security.Principal = Depends(security.require_roles("firm_admin")),
):
    if user_id == principal.user_id:
        raise envelope.validation("You cannot remove yourself from the firm.")

    member = await get_scoped_or_404(session, User, user_id, principal.tenant_id, "user")
    if member.role == "client":
        raise envelope.not_found("user")

    # Soft delete, not a hard DELETE: see the `is_active` comment on the User model
    # in app/models/entities.py — a hard delete here would cascade through the
    # member's time entries, ai jobs/conversations, devices and notifications
    # (ondelete="CASCADE"), destroying case/billing history that belongs to the firm,
    # not to the departing individual.
    member.is_active = False
    await session.commit()
    return envelope.ok({"ok": True})
