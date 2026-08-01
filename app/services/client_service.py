from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ClientNotFoundException
from app.db.tenant import TenantContext
from app.models.client import Client


async def list_clients(
    session: AsyncSession,
    tenant: TenantContext,
    *,
    q: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[Client], int]:
    stmt = select(Client).where(Client.tenant_id == tenant.tenant_id)

    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(Client.name.ilike(like), Client.phone.ilike(like), Client.email.ilike(like))
        )

    count_stmt = select(Client.id).where(Client.tenant_id == tenant.tenant_id)
    if q:
        like = f"%{q}%"
        count_stmt = count_stmt.where(
            or_(Client.name.ilike(like), Client.phone.ilike(like), Client.email.ilike(like))
        )
    total = len((await session.execute(count_stmt)).all())

    stmt = stmt.order_by(Client.created_at.desc()).limit(limit).offset(offset)
    result = await session.execute(stmt)

    return list(result.scalars().all()), total


async def get_client_or_404(
    session: AsyncSession, tenant: TenantContext, client_id: UUID
) -> Client:
    result = await session.execute(
        select(Client)
        .where(Client.id == client_id)
        .where(Client.tenant_id == tenant.tenant_id)
    )
    client = result.scalar_one_or_none()
    if client is None:
        raise ClientNotFoundException()
    return client


async def create_client(
    session: AsyncSession,
    tenant: TenantContext,
    *,
    name: str,
    phone: str | None,
    email: str | None,
    address: str | None,
    tags: list[str],
) -> Client:
    client = Client(
        tenant_id=tenant.tenant_id,
        name=name,
        phone=phone,
        email=email,
        address=address,
        tags=tags,
    )
    session.add(client)
    await session.commit()
    await session.refresh(client)
    return client


async def update_client(session: AsyncSession, client: Client, **fields) -> Client:
    for key, value in fields.items():
        if value is not None:
            setattr(client, key, value)
    await session.commit()
    await session.refresh(client)
    return client


async def delete_client(session: AsyncSession, client: Client) -> None:
    await session.delete(client)
    await session.commit()


async def invite_client(
    session: AsyncSession, tenant: TenantContext, client: Client
) -> Client:
    """
    Creates (or links) a role="client" User for portal access, per
    contract B.4: "Clients are invited ... the client logs in with the
    same OTP flow and gets role=client scoped to their own cases only."

    The actual SMS-with-code delivery is handled by the same OTP
    request/verify flow (module M3); this just provisions the account
    so the phone number can log in.
    """
    from app.models.user import User

    if not client.phone:
        raise ClientNotFoundException(
            message="Client has no phone number on file; cannot invite."
        )

    if client.user_id is not None:
        return client

    result = await session.execute(
        select(User)
        .where(User.phone == client.phone)
        .where(User.tenant_id == tenant.tenant_id)
    )
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            tenant_id=tenant.tenant_id,
            phone=client.phone,
            name=client.name,
            role="client",
            language="en",
        )
        session.add(user)
        await session.flush()

    client.user_id = user.id
    await session.commit()
    await session.refresh(client)

    return client
