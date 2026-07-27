"""B.6 calendar: hearings grouped by day, and the Today dashboard call.

Everything here is calendar-date arithmetic in IST. The server decides what "today"
means rather than trusting the device, because a lawyer whose phone is on the wrong
timezone must still see the court's day.
"""

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_scoped_or_404
from app.core import envelope, security
from app.core.db import get_session, scoped
from app.models import Case, Hearing, Notification, Task
from app.schemas.core import (
    CalendarDay,
    HearingOut,
    TaskCreate,
    TaskOut,
    TaskUpdate,
    TodayHearingOut,
    TodayOut,
)

router = APIRouter(tags=["calendar"])

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
MAX_RANGE_DAYS = 366


def today_ist() -> dt.date:
    return dt.datetime.now(IST).date()


@router.get("/calendar")
async def calendar_range(
    from_: dt.date = Query(..., alias="from"),
    to: dt.date = Query(...),
    session: AsyncSession = Depends(get_session),
    principal: security.Principal = Depends(security.require_staff),
):
    if to < from_:
        raise envelope.validation("The end date must be on or after the start date.")
    if (to - from_).days > MAX_RANGE_DAYS:
        raise envelope.validation("Please request a year or less at a time.")

    rows = (
        await session.scalars(
            scoped(Hearing, principal.tenant_id)
            .where(Hearing.date >= from_, Hearing.date <= to)
            .order_by(Hearing.date, Hearing.time.nulls_last())
        )
    ).all()

    grouped: dict[dt.date, list[Hearing]] = {}
    for hearing in rows:
        grouped.setdefault(hearing.date, []).append(hearing)

    days = [
        CalendarDay(
            date=day,
            hearings=[HearingOut.model_validate(h) for h in items],
        )
        for day, items in sorted(grouped.items())
    ]
    return envelope.ok([d.model_dump(mode="json") for d in days])


@router.get("/calendar/today")
async def calendar_today(
    session: AsyncSession = Depends(get_session),
    principal: security.Principal = Depends(security.require_staff),
):
    """The Today screen's single call (D.6) — the retention screen, so it returns
    everything that screen needs in one round trip rather than four."""
    today = today_ist()
    tomorrow = today + dt.timedelta(days=1)

    todays = (
        await session.execute(
            select(Hearing, Case.title, Case.court_name)
            .join(Case, Case.id == Hearing.case_id)
            .where(Hearing.tenant_id == principal.tenant_id, Hearing.date == today)
            .order_by(Hearing.time.nulls_last())
        )
    ).all()

    tomorrow_count = await session.scalar(
        select(func.count())
        .select_from(Hearing)
        .where(Hearing.tenant_id == principal.tenant_id, Hearing.date == tomorrow)
    )

    unread = await session.scalar(
        select(func.count())
        .select_from(Notification)
        .where(
            Notification.tenant_id == principal.tenant_id,
            Notification.user_id == principal.user_id,
            Notification.read_at.is_(None),
        )
    )

    # D.6: "Kal ki hearing ka outcome update karein" — past hearings with nothing
    # recorded. Capped and recent-first so the nudge stays actionable instead of
    # becoming a wall of every hearing the firm has ever missed.
    overdue = (
        await session.execute(
            select(Hearing, Case.title, Case.court_name)
            .join(Case, Case.id == Hearing.case_id)
            .where(
                Hearing.tenant_id == principal.tenant_id,
                Hearing.date < today,
                Hearing.date >= today - dt.timedelta(days=14),
                Hearing.outcome_notes.is_(None),
            )
            .order_by(Hearing.date.desc())
            .limit(5)
        )
    ).all()

    payload = TodayOut(
        date=today,
        hearings=[_with_case(row) for row in todays],
        tomorrow_count=tomorrow_count or 0,
        unread_notifications=unread or 0,
        overdue_outcomes=[_with_case(row) for row in overdue],
    )
    return envelope.ok(payload.model_dump(mode="json"))


def _with_case(row) -> TodayHearingOut:
    hearing, case_title, court_name = row
    return TodayHearingOut(
        **HearingOut.model_validate(hearing).model_dump(),
        case_title=case_title,
        court_name=court_name,
    )


@router.get("/tasks")
async def list_tasks(
    status: str | None = Query(None, pattern="^(open|in_progress|done)$"),
    case_id: uuid.UUID | None = None,
    session: AsyncSession = Depends(get_session),
    principal: security.Principal = Depends(security.require_staff),
):
    """D.4: the Today screen's task strip, and the case detail task list."""
    statement = scoped(Task, principal.tenant_id)
    if status:
        statement = statement.where(Task.status == status)
    if case_id:
        statement = statement.where(Task.case_id == case_id)

    rows = (
        await session.scalars(statement.order_by(Task.due_date.nulls_last(), Task.created_at))
    ).all()
    return envelope.ok([TaskOut.model_validate(t).model_dump(mode="json") for t in rows])


@router.post("/tasks")
async def create_task(
    body: TaskCreate,
    session: AsyncSession = Depends(get_session),
    principal: security.Principal = Depends(security.require_staff),
):
    if body.case_id is not None:
        case = await session.get(Case, body.case_id)
        if case is None or case.tenant_id != principal.tenant_id:
            raise envelope.not_found("case")

    task = Task(
        tenant_id=principal.tenant_id,
        created_by=principal.user_id,
        # Unassigned tasks default to the person creating them: in a solo practice
        # that is always right, and in a firm it is the sane default to edit.
        assignee_id=body.assignee_id or principal.user_id,
        title=body.title,
        case_id=body.case_id,
        due_date=body.due_date,
        status="open",
    )
    session.add(task)
    await session.commit()
    await session.refresh(task)
    return envelope.ok(TaskOut.model_validate(task).model_dump(mode="json"))


@router.patch("/tasks/{task_id}")
async def update_task(
    task_id: uuid.UUID,
    body: TaskUpdate,
    session: AsyncSession = Depends(get_session),
    principal: security.Principal = Depends(security.require_staff),
):
    task = await get_scoped_or_404(session, Task, task_id, principal.tenant_id, "task")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(task, field, value)

    await session.commit()
    await session.refresh(task)
    return envelope.ok(TaskOut.model_validate(task).model_dump(mode="json"))
