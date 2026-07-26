"""Shared router helpers: pagination and tenant-scoped fetch-or-404."""

from typing import Any
from uuid import UUID

from fastapi import Query
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import envelope
from app.core.envelope import PageMeta

MAX_LIMIT = 100


class Page:
    """`?page=1&limit=20`, max limit 100 (B.3)."""

    def __init__(
        self,
        page: int = Query(1, ge=1),
        limit: int = Query(20, ge=1, le=MAX_LIMIT),
    ) -> None:
        self.page = page
        self.limit = limit

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.limit


async def paginate(
    session: AsyncSession,
    statement: Select,
    page: Page,
) -> tuple[list[Any], PageMeta]:
    total = await session.scalar(
        select(func.count()).select_from(statement.subquery())
    )
    rows = (
        await session.scalars(statement.offset(page.offset).limit(page.limit))
    ).all()
    return list(rows), PageMeta(page=page.page, limit=page.limit, total=total or 0)


async def get_scoped_or_404[ModelT](
    session: AsyncSession,
    model: type[ModelT],
    entity_id: UUID,
    tenant_id: UUID,
    resource: str,
) -> ModelT:
    """Fetch by id **and** tenant.

    Checking the tenant here rather than trusting the id is the difference between
    "not found" and a cross-tenant read: an attacker who guesses a UUID from another
    firm must get a 404, not that firm's case.
    """
    entity = await session.get(model, entity_id)
    if entity is None or getattr(entity, "tenant_id", None) != tenant_id:
        raise envelope.not_found(resource)
    return entity
