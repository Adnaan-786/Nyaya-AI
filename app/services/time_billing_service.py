from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.tenant import TenantContext
from app.models.expense import Expense
from app.models.time_entry import TimeEntry


async def list_time_entries(
    session: AsyncSession,
    tenant: TenantContext,
    *,
    case_id: UUID | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[TimeEntry], int]:
    stmt = select(TimeEntry).where(TimeEntry.tenant_id == tenant.tenant_id)
    count_stmt = select(TimeEntry.id).where(TimeEntry.tenant_id == tenant.tenant_id)

    if case_id:
        stmt = stmt.where(TimeEntry.case_id == case_id)
        count_stmt = count_stmt.where(TimeEntry.case_id == case_id)

    total = len((await session.execute(count_stmt)).all())

    stmt = stmt.order_by(TimeEntry.date.desc()).limit(limit).offset(offset)
    result = await session.execute(stmt)

    return list(result.scalars().all()), total


async def create_time_entry(
    session: AsyncSession,
    tenant: TenantContext,
    *,
    user_id: UUID,
    case_id: UUID,
    date,
    duration_minutes: int,
    description: str | None,
) -> TimeEntry:
    entry = TimeEntry(
        tenant_id=tenant.tenant_id,
        case_id=case_id,
        user_id=user_id,
        date=date,
        duration_minutes=duration_minutes,
        description=description,
    )
    session.add(entry)
    await session.commit()
    await session.refresh(entry)
    return entry


async def list_expenses(
    session: AsyncSession,
    tenant: TenantContext,
    *,
    case_id: UUID | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[Expense], int]:
    stmt = select(Expense).where(Expense.tenant_id == tenant.tenant_id)
    count_stmt = select(Expense.id).where(Expense.tenant_id == tenant.tenant_id)

    if case_id:
        stmt = stmt.where(Expense.case_id == case_id)
        count_stmt = count_stmt.where(Expense.case_id == case_id)

    total = len((await session.execute(count_stmt)).all())

    stmt = stmt.order_by(Expense.expense_date.desc()).limit(limit).offset(offset)
    result = await session.execute(stmt)

    return list(result.scalars().all()), total


async def create_expense(
    session: AsyncSession,
    tenant: TenantContext,
    *,
    case_id: UUID | None,
    amount_paise: int,
    category: str,
    expense_date,
    description: str | None,
) -> Expense:
    expense = Expense(
        tenant_id=tenant.tenant_id,
        case_id=case_id,
        amount_paise=amount_paise,
        category=category,
        expense_date=expense_date,
        description=description,
    )
    session.add(expense)
    await session.commit()
    await session.refresh(expense)
    return expense
