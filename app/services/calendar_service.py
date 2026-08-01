import datetime
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import AuthContext
from app.models.case_assignee import CaseAssignee
from app.models.hearing import Hearing


async def get_hearings_in_range(
    session: AsyncSession,
    auth: AuthContext,
    *,
    date_from: datetime.date,
    date_to: datetime.date,
) -> dict[str, list[Hearing]]:
    stmt = (
        select(Hearing)
        .where(Hearing.tenant_id == auth.tenant_id)
        .where(Hearing.date >= date_from)
        .where(Hearing.date <= date_to)
    )

    # firm_admin sees every hearing in the firm; other roles only see
    # hearings for cases they're assigned to (contract B.6: "across
    # all assigned cases").
    if auth.role != "firm_admin":
        stmt = stmt.join(
            CaseAssignee, CaseAssignee.case_id == Hearing.case_id
        ).where(CaseAssignee.user_id == auth.user_id)

    stmt = stmt.order_by(Hearing.date.asc(), Hearing.time.asc().nulls_last())

    result = await session.execute(stmt)
    hearings = list(result.scalars().all())

    grouped: dict[str, list[Hearing]] = defaultdict(list)
    for h in hearings:
        grouped[h.date.isoformat()].append(h)

    return dict(grouped)
