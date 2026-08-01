from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import UserNotFoundException, ValidationException
from app.db.tenant import TenantContext
from app.models.tenant import Tenant
from app.models.user import User

VALID_MEMBER_ROLES = {"firm_admin", "lawyer", "intern"}


async def get_firm(session: AsyncSession, tenant: TenantContext) -> Tenant:
    result = await session.execute(select(Tenant).where(Tenant.id == tenant.tenant_id))
    firm = result.scalar_one_or_none()
    if firm is None:
        raise ValidationException("Firm not found.")
    return firm


async def update_firm(session: AsyncSession, firm: Tenant, *, name: str | None) -> Tenant:
    if name:
        firm.name = name
    await session.commit()
    await session.refresh(firm)
    return firm


async def list_members(session: AsyncSession, tenant: TenantContext) -> list[User]:
    result = await session.execute(
        select(User)
        .where(User.tenant_id == tenant.tenant_id)
        .where(User.role.in_(VALID_MEMBER_ROLES))
        .order_by(User.created_at.asc())
    )
    return list(result.scalars().all())


async def invite_member(
    session: AsyncSession,
    tenant: TenantContext,
    *,
    phone: str,
    name: str,
    role: str,
) -> User:
    if role not in VALID_MEMBER_ROLES:
        raise ValidationException(
            "role must be one of: firm_admin, lawyer, intern.",
            details={"allowed_roles": sorted(VALID_MEMBER_ROLES)},
        )

    result = await session.execute(
        select(User)
        .where(User.phone == phone)
        .where(User.tenant_id == tenant.tenant_id)
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        return existing

    member = User(
        tenant_id=tenant.tenant_id,
        phone=phone,
        name=name,
        role=role,
        language="en",
    )
    session.add(member)
    await session.commit()
    await session.refresh(member)
    return member


async def get_member_or_404(
    session: AsyncSession, tenant: TenantContext, user_id: UUID
) -> User:
    result = await session.execute(
        select(User).where(User.id == user_id).where(User.tenant_id == tenant.tenant_id)
    )
    member = result.scalar_one_or_none()
    if member is None:
        raise UserNotFoundException()
    return member


async def change_member_role(session: AsyncSession, member: User, *, role: str) -> User:
    if role not in VALID_MEMBER_ROLES:
        raise ValidationException(
            "role must be one of: firm_admin, lawyer, intern.",
            details={"allowed_roles": sorted(VALID_MEMBER_ROLES)},
        )
    member.role = role
    await session.commit()
    await session.refresh(member)
    return member


async def remove_member(session: AsyncSession, member: User) -> None:
    await session.delete(member)
    await session.commit()
