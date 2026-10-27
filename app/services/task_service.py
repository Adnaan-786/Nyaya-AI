from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationException
from app.db.enums import NotificationType
from app.db.tenant import TenantContext
from app.models.task import Task
from app.models.user import User
from app.services.notification_dispatch_service import notify
from app.services.notification_templates import task_assigned_copy


async def list_tasks(
    session: AsyncSession,
    tenant: TenantContext,
    *,
    assignee: UUID | None = None,
    status: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[Task], int]:
    stmt = select(Task).where(Task.tenant_id == tenant.tenant_id)
    count_stmt = select(Task.id).where(Task.tenant_id == tenant.tenant_id)

    if assignee:
        stmt = stmt.where(Task.assigned_to == assignee)
        count_stmt = count_stmt.where(Task.assigned_to == assignee)

    if status:
        stmt = stmt.where(Task.status == status)
        count_stmt = count_stmt.where(Task.status == status)

    total = len((await session.execute(count_stmt)).all())

    stmt = stmt.order_by(Task.due_date.asc().nulls_last()).limit(limit).offset(offset)
    result = await session.execute(stmt)

    return list(result.scalars().all()), total


async def get_task_or_404(session: AsyncSession, tenant: TenantContext, task_id: UUID) -> Task:
    result = await session.execute(
        select(Task).where(Task.id == task_id).where(Task.tenant_id == tenant.tenant_id)
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise ValidationException("Task not found.")
    return task


async def create_task(
    session: AsyncSession,
    tenant: TenantContext,
    *,
    case_id: UUID | None,
    title: str,
    assignee_id: UUID,
    due_date,
    description: str | None,
    created_by: UUID | None = None,
) -> Task:
    task = Task(
        tenant_id=tenant.tenant_id,
        case_id=case_id,
        assigned_to=assignee_id,
        title=title,
        due_date=due_date,
        description=description,
        created_by=created_by,
    )
    session.add(task)
    await session.commit()
    await session.refresh(task)

    if created_by is not None and assignee_id != created_by:
        result = await session.execute(select(User).where(User.id == assignee_id))
        assignee = result.scalar_one_or_none()
        language = assignee.language if assignee else "en"

        title_copy, body_copy = task_assigned_copy(task_title=title, language=language)
        await notify(
            session,
            tenant_id=tenant.tenant_id,
            user_id=assignee_id,
            type=NotificationType.TASK_ASSIGNED,
            title=title_copy,
            body=body_copy,
            data={"task_id": str(task.id)},
            channels={"push"},
        )

    return task


async def update_task(session: AsyncSession, task: Task, **fields) -> Task:
    for key, value in fields.items():
        if value is not None:
            setattr(task, key, value)
    await session.commit()
    await session.refresh(task)
    return task
