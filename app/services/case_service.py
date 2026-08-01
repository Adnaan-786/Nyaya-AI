import re
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import CaseNotFoundException, CNRInvalidException
from app.db.tenant import TenantContext
from app.models.case import Case
from app.models.case_assignee import CaseAssignee

CNR_PATTERN = re.compile(r"^[A-Za-z0-9]{16}$")


def validate_cnr(cnr: str) -> None:
    """16-char alphanumeric CNR format (contract B.6/C.6)."""
    if not CNR_PATTERN.match(cnr):
        raise CNRInvalidException(
            message="CNR must be exactly 16 alphanumeric characters.",
            details={"cnr": cnr},
        )


async def list_cases(
    session: AsyncSession,
    tenant: TenantContext,
    *,
    status: str | None = None,
    court: str | None = None,
    assigned_to: UUID | None = None,
    client_id: UUID | None = None,
    q: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[Case], int]:
    stmt = select(Case).where(Case.tenant_id == tenant.tenant_id)
    count_stmt = select(Case.id).where(Case.tenant_id == tenant.tenant_id)

    if client_id:
        stmt = stmt.where(Case.client_id == client_id)
        count_stmt = count_stmt.where(Case.client_id == client_id)

    if status:
        stmt = stmt.where(Case.status == status)
        count_stmt = count_stmt.where(Case.status == status)

    if court:
        stmt = stmt.where(Case.court_name == court)
        count_stmt = count_stmt.where(Case.court_name == court)

    if q:
        like = f"%{q}%"
        cond = or_(Case.title.ilike(like), Case.case_number.ilike(like), Case.cnr.ilike(like))
        stmt = stmt.where(cond)
        count_stmt = count_stmt.where(cond)

    if assigned_to:
        stmt = stmt.join(CaseAssignee, CaseAssignee.case_id == Case.id).where(
            CaseAssignee.user_id == assigned_to
        )
        count_stmt = count_stmt.join(
            CaseAssignee, CaseAssignee.case_id == Case.id
        ).where(CaseAssignee.user_id == assigned_to)

    total = len((await session.execute(count_stmt)).all())

    stmt = stmt.order_by(Case.created_at.desc()).limit(limit).offset(offset)
    result = await session.execute(stmt)

    return list(result.scalars().all()), total


async def get_case_or_404(session: AsyncSession, tenant: TenantContext, case_id: UUID) -> Case:
    result = await session.execute(
        select(Case).where(Case.id == case_id).where(Case.tenant_id == tenant.tenant_id)
    )
    case = result.scalar_one_or_none()
    if case is None:
        raise CaseNotFoundException()
    return case


async def create_case(
    session: AsyncSession,
    tenant: TenantContext,
    *,
    title: str,
    client_id: UUID,
    case_number: str | None,
    court_name: str | None,
    court_type: str | None,
    judge_name: str | None,
    case_type: str | None,
    stage: str | None,
    next_hearing_date,
    assigned_user_ids: list[UUID],
) -> Case:
    case = Case(
        tenant_id=tenant.tenant_id,
        title=title,
        client_id=client_id,
        case_number=case_number,
        court_name=court_name,
        court_type=court_type,
        judge_name=judge_name,
        case_type=case_type,
        stage=stage,
        next_hearing_date=next_hearing_date,
        ecourts_synced=False,
    )
    session.add(case)
    await session.flush()

    for user_id in set(assigned_user_ids):
        session.add(CaseAssignee(case_id=case.id, user_id=user_id))

    await session.commit()
    await session.refresh(case)

    return case


async def update_case(session: AsyncSession, case: Case, **fields) -> Case:
    for key, value in fields.items():
        if value is not None:
            setattr(case, key, value)
    await session.commit()
    await session.refresh(case)
    return case


async def delete_case(session: AsyncSession, case: Case) -> None:
    """Soft delete per plan C.6: archive rather than hard-delete."""
    case.status = "archived"
    await session.commit()
