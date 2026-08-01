from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import AuthContext, get_tenant_scoped_db
from app.core.rbac import require
from app.core.responses import ApiResponse, Meta
from app.schemas.casework import TaskCreateIn, TaskOut, TaskUpdateIn
from app.services import task_service

router = APIRouter(prefix="/tasks", tags=["Tasks"])


@router.get("", response_model=ApiResponse[list[TaskOut]])
async def list_tasks(
    assignee: UUID | None = None,
    status: str | None = None,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    auth: AuthContext = Depends(require("tasks.read")),
    session: AsyncSession = Depends(get_tenant_scoped_db),
) -> ApiResponse[list[TaskOut]]:
    tenant = auth.as_tenant_context()
    tasks, total = await task_service.list_tasks(
        session, tenant, assignee=assignee, status=status, limit=limit, offset=(page - 1) * limit
    )
    return ApiResponse(
        success=True,
        data=[TaskOut.model_validate(t) for t in tasks],
        meta=Meta(page=page, limit=limit, total=total),
    )


@router.post("", response_model=ApiResponse[TaskOut])
async def create_task(
    payload: TaskCreateIn,
    auth: AuthContext = Depends(require("tasks.write")),
    session: AsyncSession = Depends(get_tenant_scoped_db),
) -> ApiResponse[TaskOut]:
    tenant = auth.as_tenant_context()
    task = await task_service.create_task(
        session,
        tenant,
        case_id=payload.case_id,
        title=payload.title,
        assignee_id=payload.assignee_id,
        due_date=payload.due_date,
        description=payload.description,
    )
    return ApiResponse(success=True, data=TaskOut.model_validate(task))


@router.patch("/{task_id}", response_model=ApiResponse[TaskOut])
async def update_task(
    task_id: UUID,
    payload: TaskUpdateIn,
    auth: AuthContext = Depends(require("tasks.write")),
    session: AsyncSession = Depends(get_tenant_scoped_db),
) -> ApiResponse[TaskOut]:
    tenant = auth.as_tenant_context()
    task = await task_service.get_task_or_404(session, tenant, task_id)
    task = await task_service.update_task(session, task, **payload.model_dump())
    return ApiResponse(success=True, data=TaskOut.model_validate(task))
