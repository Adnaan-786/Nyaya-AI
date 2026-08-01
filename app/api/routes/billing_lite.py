from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import AuthContext, get_tenant_scoped_db
from app.core.rbac import require
from app.core.responses import ApiResponse, Meta
from app.schemas.casework import (
    ExpenseCreateIn,
    ExpenseOut,
    TimeEntryCreateIn,
    TimeEntryOut,
)
from app.services import time_billing_service

router = APIRouter(tags=["Billing (time & expenses)"])


@router.get("/time-entries", response_model=ApiResponse[list[TimeEntryOut]])
async def list_time_entries(
    case_id: UUID | None = None,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    auth: AuthContext = Depends(require("billing.read")),
    session: AsyncSession = Depends(get_tenant_scoped_db),
) -> ApiResponse[list[TimeEntryOut]]:
    tenant = auth.as_tenant_context()
    entries, total = await time_billing_service.list_time_entries(
        session, tenant, case_id=case_id, limit=limit, offset=(page - 1) * limit
    )
    return ApiResponse(
        success=True,
        data=[TimeEntryOut.model_validate(e) for e in entries],
        meta=Meta(page=page, limit=limit, total=total),
    )


@router.post("/time-entries", response_model=ApiResponse[TimeEntryOut])
async def create_time_entry(
    payload: TimeEntryCreateIn,
    auth: AuthContext = Depends(require("billing.write")),
    session: AsyncSession = Depends(get_tenant_scoped_db),
) -> ApiResponse[TimeEntryOut]:
    tenant = auth.as_tenant_context()
    entry = await time_billing_service.create_time_entry(
        session,
        tenant,
        user_id=auth.user_id,
        case_id=payload.case_id,
        date=payload.date,
        duration_minutes=payload.duration_minutes,
        description=payload.description,
    )
    return ApiResponse(success=True, data=TimeEntryOut.model_validate(entry))


@router.get("/expenses", response_model=ApiResponse[list[ExpenseOut]])
async def list_expenses(
    case_id: UUID | None = None,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    auth: AuthContext = Depends(require("billing.read")),
    session: AsyncSession = Depends(get_tenant_scoped_db),
) -> ApiResponse[list[ExpenseOut]]:
    tenant = auth.as_tenant_context()
    expenses, total = await time_billing_service.list_expenses(
        session, tenant, case_id=case_id, limit=limit, offset=(page - 1) * limit
    )
    return ApiResponse(
        success=True,
        data=[ExpenseOut.model_validate(e) for e in expenses],
        meta=Meta(page=page, limit=limit, total=total),
    )


@router.post("/expenses", response_model=ApiResponse[ExpenseOut])
async def create_expense(
    payload: ExpenseCreateIn,
    auth: AuthContext = Depends(require("billing.write")),
    session: AsyncSession = Depends(get_tenant_scoped_db),
) -> ApiResponse[ExpenseOut]:
    tenant = auth.as_tenant_context()
    expense = await time_billing_service.create_expense(
        session,
        tenant,
        case_id=payload.case_id,
        amount_paise=payload.amount_paise,
        category=payload.category,
        expense_date=payload.expense_date,
        description=payload.description,
    )
    return ApiResponse(success=True, data=ExpenseOut.model_validate(expense))
