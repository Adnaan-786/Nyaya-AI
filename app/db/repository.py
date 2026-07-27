from typing import Any, Generic, TypeVar
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.tenant import TenantContext

ModelType = TypeVar("ModelType")


class Repository(Generic[ModelType]):
    def __init__(
        self,
        session: AsyncSession,
        tenant: TenantContext,
        model: type[ModelType],
    ):
        self.session = session
        self.tenant = tenant
        self.model = model

    async def get(
        self,
        id: UUID,
    ) -> ModelType | None:
        stmt = (
            select(self.model)
            .where(self.model.id == id)
            .where(self.model.tenant_id == self.tenant.tenant_id)
        )

        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ModelType]:
        stmt = (
            select(self.model)
            .where(self.model.tenant_id == self.tenant.tenant_id)
            .limit(limit)
            .offset(offset)
        )

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(
        self,
        **kwargs: Any,
    ) -> ModelType:
        obj = self.model(
            tenant_id=self.tenant.tenant_id,
            **kwargs,
        )

        self.session.add(obj)
        await self.session.flush()
        await self.session.refresh(obj)

        return obj

    async def update(
        self,
        obj: ModelType,
        **kwargs: Any,
    ) -> ModelType:
        for key, value in kwargs.items():
            setattr(obj, key, value)

        await self.session.flush()
        await self.session.refresh(obj)

        return obj

    async def delete(
        self,
        obj: ModelType,
    ) -> None:
        await self.session.delete(obj)
        await self.session.flush()

    async def exists(
        self,
        id: UUID,
    ) -> bool:
        stmt = (
            select(self.model.id)
            .where(self.model.id == id)
            .where(self.model.tenant_id == self.tenant.tenant_id)
        )

        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def count(self) -> int:
        stmt = (
            select(func.count())
            .select_from(self.model)
            .where(self.model.tenant_id == self.tenant.tenant_id)
        )

        result = await self.session.execute(stmt)
        return int(result.scalar_one())

    async def filter(
        self,
        **filters: Any,
    ) -> list[ModelType]:
        stmt = select(self.model).where(
            self.model.tenant_id == self.tenant.tenant_id
        )

        for field, value in filters.items():
            stmt = stmt.where(
                getattr(self.model, field) == value
            )

        result = await self.session.execute(stmt)
        return list(result.scalars().all())