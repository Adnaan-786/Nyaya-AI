"""B.6 clients, plus the portal invite that creates a client-role login."""

import secrets
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Page, get_scoped_or_404, paginate
from app.core import envelope, security
from app.core.db import get_session, scoped
from app.integrations import sms
from app.models import Case, Client, User
from app.schemas.core import CaseOut, ClientCreate, ClientOut, ClientUpdate

router = APIRouter(tags=["clients"])


@router.get("/clients")
async def list_clients(
    q: str | None = Query(None, description="Search name, phone or email"),
    page: Page = Depends(),
    session: AsyncSession = Depends(get_session),
    principal: security.Principal = Depends(security.require_staff),
):
    statement = scoped(Client, principal.tenant_id)
    if q:
        pattern = f"%{q.strip()}%"
        statement = statement.where(
            or_(
                Client.name.ilike(pattern),
                Client.phone.ilike(pattern),
                Client.email.ilike(pattern),
            )
        )
    statement = statement.order_by(Client.name)

    rows, meta = await paginate(session, statement, page)
    return envelope.ok(
        [ClientOut.model_validate(r).model_dump(mode="json") for r in rows], meta
    )


@router.post("/clients")
async def create_client(
    body: ClientCreate,
    session: AsyncSession = Depends(get_session),
    principal: security.Principal = Depends(security.require_staff),
):
    client = Client(tenant_id=principal.tenant_id, **body.model_dump())
    session.add(client)
    await session.commit()
    await session.refresh(client)
    return envelope.ok(ClientOut.model_validate(client).model_dump(mode="json"))


@router.get("/clients/{client_id}")
async def get_client(
    client_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    principal: security.Principal = Depends(security.require_staff),
):
    client = await get_scoped_or_404(session, Client, client_id, principal.tenant_id, "client")
    return envelope.ok(ClientOut.model_validate(client).model_dump(mode="json"))


@router.patch("/clients/{client_id}")
async def update_client(
    client_id: uuid.UUID,
    body: ClientUpdate,
    session: AsyncSession = Depends(get_session),
    principal: security.Principal = Depends(security.require_staff),
):
    client = await get_scoped_or_404(session, Client, client_id, principal.tenant_id, "client")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(client, field, value)
    await session.commit()
    await session.refresh(client)
    return envelope.ok(ClientOut.model_validate(client).model_dump(mode="json"))


@router.delete("/clients/{client_id}")
async def delete_client(
    client_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    principal: security.Principal = Depends(security.require_staff),
):
    client = await get_scoped_or_404(session, Client, client_id, principal.tenant_id, "client")
    await session.delete(client)
    await session.commit()
    return envelope.ok({"ok": True})


@router.get("/clients/{client_id}/cases")
async def client_cases(
    client_id: uuid.UUID,
    page: Page = Depends(),
    session: AsyncSession = Depends(get_session),
    principal: security.Principal = Depends(security.require_staff),
):
    await get_scoped_or_404(session, Client, client_id, principal.tenant_id, "client")
    statement = (
        scoped(Case, principal.tenant_id)
        .where(Case.client_id == client_id)
        .order_by(Case.next_hearing_date.nulls_last())
    )
    rows, meta = await paginate(session, statement, page)
    return envelope.ok(
        [CaseOut.model_validate(r).model_dump(mode="json") for r in rows], meta
    )


@router.post("/clients/{client_id}/invite")
async def invite_client(
    client_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    principal: security.Principal = Depends(security.require_staff),
):
    """B.4: the client logs in through the same OTP flow and gets `role=client`,
    scoped to their own cases. There is no separate client app or base URL — the
    server filters everything by identity."""
    client = await get_scoped_or_404(session, Client, client_id, principal.tenant_id, "client")

    existing = (
        await session.scalars(select(User).where(User.phone == client.phone))
    ).first()

    if existing is None:
        user = User(
            tenant_id=principal.tenant_id,
            name=client.name,
            phone=client.phone,
            role="client",
            client_id=client.id,
        )
        session.add(user)
    else:
        # Re-inviting must not silently demote a lawyer who happens to share a number
        # with a client record — that would lock them out of their own firm.
        if existing.role != "client":
            raise envelope.duplicate(
                "That number already belongs to a team member in your firm."
            )
        existing.client_id = client.id
        user = existing

    await session.commit()

    code = secrets.token_hex(3).upper()
    await sms.send_text(
        client.phone,
        f"{client.name}, you can now follow your case with NyayaAI. "
        f"Sign in with this number. Reference: {code}",
    )
    return envelope.ok({"ok": True, "invited_phone": client.phone})
