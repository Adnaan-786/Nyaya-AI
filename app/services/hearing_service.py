from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationException
from app.db.tenant import TenantContext
from app.models.case_note import CaseNote
from app.models.hearing import Hearing


async def list_hearings(
    session: AsyncSession, tenant: TenantContext, case_id: UUID
) -> list[Hearing]:
    result = await session.execute(
        select(Hearing)
        .where(Hearing.case_id == case_id)
        .where(Hearing.tenant_id == tenant.tenant_id)
        .order_by(Hearing.date.asc())
    )
    return list(result.scalars().all())


async def create_hearing(
    session: AsyncSession,
    tenant: TenantContext,
    case_id: UUID,
    *,
    date,
    time,
    purpose: str | None,
    courtroom: str | None,
) -> Hearing:
    hearing = Hearing(
        tenant_id=tenant.tenant_id,
        case_id=case_id,
        date=date,
        time=time,
        purpose=purpose,
        courtroom=courtroom,
        source="manual",
    )
    session.add(hearing)
    await session.commit()
    await session.refresh(hearing)
    return hearing


async def get_hearing_or_404(
    session: AsyncSession, tenant: TenantContext, hearing_id: UUID
) -> Hearing:
    result = await session.execute(
        select(Hearing)
        .where(Hearing.id == hearing_id)
        .where(Hearing.tenant_id == tenant.tenant_id)
    )
    hearing = result.scalar_one_or_none()
    if hearing is None:
        raise ValidationException("Hearing not found.")
    return hearing


async def update_hearing(session: AsyncSession, hearing: Hearing, **fields) -> Hearing:
    for key, value in fields.items():
        if value is not None:
            setattr(hearing, key, value)
    await session.commit()
    await session.refresh(hearing)
    return hearing


async def add_case_note(
    session: AsyncSession,
    tenant: TenantContext,
    case_id: UUID,
    *,
    author_id: UUID | None,
    text: str,
) -> CaseNote:
    note = CaseNote(
        tenant_id=tenant.tenant_id,
        case_id=case_id,
        author_id=author_id,
        text=text,
    )
    session.add(note)
    await session.commit()
    await session.refresh(note)
    return note


async def get_case_timeline(
    session: AsyncSession, tenant: TenantContext, case_id: UUID
) -> list[dict]:
    """
    Merged, descending-order read model of hearings + notes for a case
    (contract B.6: "merged events: hearings, docs, notes, status changes").
    Document/status-change events are added once M6/M4-status-history
    land; this returns hearings + notes today.
    """

    hearings = await list_hearings(session, tenant, case_id)

    notes_result = await session.execute(
        select(CaseNote)
        .where(CaseNote.case_id == case_id)
        .where(CaseNote.tenant_id == tenant.tenant_id)
    )
    notes = list(notes_result.scalars().all())

    events: list[dict] = []

    for h in hearings:
        at = h.created_at
        events.append(
            {
                "type": "hearing",
                "at": at,
                "data": {
                    "id": str(h.id),
                    "date": h.date.isoformat(),
                    "purpose": h.purpose,
                    "courtroom": h.courtroom,
                    "outcome_notes": h.outcome_notes,
                    "source": h.source.value if hasattr(h.source, "value") else h.source,
                },
            }
        )

    for n in notes:
        events.append(
            {
                "type": "note",
                "at": n.created_at,
                "data": {
                    "id": str(n.id),
                    "text": n.text,
                    "author_id": str(n.author_id) if n.author_id else None,
                },
            }
        )

    events.sort(key=lambda e: e["at"], reverse=True)

    return events
