"""B.6 cases, hearings, notes, timeline and eCourts sync."""

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Page, get_scoped_or_404, paginate
from app.core import envelope, security
from app.core.db import get_session, scoped
from app.integrations import ecourts
from app.models import Case, CaseAssignee, CaseNote, Client, Document, Hearing
from app.schemas.core import (
    CNR_LENGTH,
    CaseCreate,
    CaseFromCnrRequest,
    CaseOut,
    CaseUpdate,
    CnrLookupRequest,
    CnrPreviewOut,
    HearingCreate,
    HearingOut,
    HearingUpdate,
    NoteCreate,
    TimelineEvent,
)

router = APIRouter(tags=["cases"])


def normalise_cnr(value: str) -> str:
    """B.3: a malformed CNR is 422 CNR_INVALID, not a generic validation error."""
    cleaned = value.strip().upper().replace(" ", "").replace("-", "")
    if len(cleaned) != CNR_LENGTH or not cleaned.isalnum():
        raise envelope.cnr_invalid()
    return cleaned

# B.6: force refresh is rate-limited to 1/hour/case. eCourts is slow and fragile;
# a pull-to-refresh gesture must not be able to hammer it.
SYNC_COOLDOWN = dt.timedelta(hours=1)


async def _to_out(session: AsyncSession, case: Case) -> dict:
    assignees = (
        await session.scalars(
            select(CaseAssignee.user_id).where(CaseAssignee.case_id == case.id)
        )
    ).all()
    payload = CaseOut.model_validate(case).model_dump(mode="json")
    payload["assigned_user_ids"] = [str(a) for a in assignees]
    return payload


@router.get("/cases")
async def list_cases(
    status: str | None = Query(None, pattern="^(active|disposed|archived)$"),
    court: str | None = None,
    assigned_to: uuid.UUID | None = None,
    q: str | None = None,
    next_hearing_before: dt.date | None = None,
    page: Page = Depends(),
    session: AsyncSession = Depends(get_session),
    principal: security.Principal = Depends(security.require_staff),
):
    statement = scoped(Case, principal.tenant_id)

    if status:
        statement = statement.where(Case.status == status)
    if court:
        statement = statement.where(Case.court_name.ilike(f"%{court}%"))
    if next_hearing_before:
        statement = statement.where(Case.next_hearing_date <= next_hearing_before)
    if assigned_to:
        statement = statement.where(
            Case.id.in_(
                select(CaseAssignee.case_id).where(CaseAssignee.user_id == assigned_to)
            )
        )
    if q:
        pattern = f"%{q.strip()}%"
        statement = statement.where(
            or_(
                Case.title.ilike(pattern),
                Case.cnr.ilike(pattern),
                Case.case_number.ilike(pattern),
                Case.court_name.ilike(pattern),
            )
        )

    # D.6: sorted by next hearing by default — the list answers "what is coming up",
    # not "what did I type in most recently".
    statement = statement.order_by(
        Case.next_hearing_date.asc().nulls_last(), Case.created_at.desc()
    )

    rows, meta = await paginate(session, statement, page)
    return envelope.ok([await _to_out(session, r) for r in rows], meta)


@router.post("/cases")
async def create_case(
    body: CaseCreate,
    session: AsyncSession = Depends(get_session),
    principal: security.Principal = Depends(security.require_staff),
):
    if body.client_id is not None:
        await get_scoped_or_404(session, Client, body.client_id, principal.tenant_id, "client")

    case = Case(tenant_id=principal.tenant_id, **body.model_dump())
    session.add(case)
    await session.flush()
    session.add(CaseAssignee(case_id=case.id, user_id=principal.user_id))
    await session.commit()
    await session.refresh(case)
    return envelope.ok(await _to_out(session, case))


@router.post("/cases/lookup-cnr")
async def lookup_cnr(
    body: CnrLookupRequest,
    _: security.Principal = Depends(security.require_staff),
):
    """Preview only — nothing is persisted until the user confirms (D.6)."""
    preview: CnrPreviewOut = await ecourts.lookup_cnr(normalise_cnr(body.cnr))
    payload = preview.model_dump(mode="json")
    # Show the history in the preview so the user can see this is the right case
    # before committing to it.
    payload["hearing_history"] = [
        {
            "id": str(uuid.uuid4()),
            "case_id": str(uuid.UUID(int=0)),
            "date": h["date"].isoformat(),
            "time": None,
            "purpose": h["purpose"],
            "courtroom": None,
            "outcome_notes": h["outcome_notes"],
            "source": "ecourts",
        }
        for h in ecourts.synth_history(normalise_cnr(body.cnr))
    ]
    return envelope.ok(payload)


@router.post("/cases/from-cnr")
async def create_case_from_cnr(
    body: CaseFromCnrRequest,
    session: AsyncSession = Depends(get_session),
    principal: security.Principal = Depends(security.require_staff),
):
    cnr = normalise_cnr(body.cnr)

    duplicate_case = (
        await session.scalars(
            scoped(Case, principal.tenant_id).where(Case.cnr == cnr)
        )
    ).first()
    if duplicate_case is not None:
        raise envelope.duplicate("That case is already in your list.")

    if body.client_id is not None:
        await get_scoped_or_404(session, Client, body.client_id, principal.tenant_id, "client")

    preview = await ecourts.lookup_cnr(cnr)
    case = Case(
        tenant_id=principal.tenant_id,
        cnr=cnr,
        title=preview.title,
        case_number=preview.case_number,
        court_name=preview.court_name,
        court_type=preview.court_type,
        judge_name=preview.judge_name,
        case_type=preview.case_type,
        stage=preview.stage,
        client_id=body.client_id,
        next_hearing_date=preview.next_hearing_date,
        ecourts_synced=True,
        last_synced_at=dt.datetime.now(dt.UTC),
        raw_ecourts=preview.model_dump(mode="json"),
    )
    session.add(case)
    await session.flush()
    session.add(CaseAssignee(case_id=case.id, user_id=principal.user_id))

    # Past hearings arrive as real rows so the case has history from the moment it is
    # added — this is what makes add-by-CNR feel like the app already knew the case.
    for entry in ecourts.synth_history(cnr):
        session.add(
            Hearing(
                tenant_id=principal.tenant_id,
                case_id=case.id,
                date=entry["date"],
                purpose=entry["purpose"],
                outcome_notes=entry["outcome_notes"],
                source="ecourts",
            )
        )
    if preview.next_hearing_date:
        session.add(
            Hearing(
                tenant_id=principal.tenant_id,
                case_id=case.id,
                date=preview.next_hearing_date,
                purpose=preview.stage,
                source="ecourts",
            )
        )

    await session.commit()
    await session.refresh(case)
    return envelope.ok(await _to_out(session, case))


@router.get("/cases/{case_id}")
async def get_case(
    case_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    principal: security.Principal = Depends(security.require_staff),
):
    case = await get_scoped_or_404(session, Case, case_id, principal.tenant_id, "case")
    return envelope.ok(await _to_out(session, case))


@router.patch("/cases/{case_id}")
async def update_case(
    case_id: uuid.UUID,
    body: CaseUpdate,
    session: AsyncSession = Depends(get_session),
    principal: security.Principal = Depends(security.require_staff),
):
    case = await get_scoped_or_404(session, Case, case_id, principal.tenant_id, "case")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(case, field, value)
    await session.commit()
    await session.refresh(case)
    return envelope.ok(await _to_out(session, case))


@router.delete("/cases/{case_id}")
async def delete_case(
    case_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    principal: security.Principal = Depends(security.require_staff),
):
    case = await get_scoped_or_404(session, Case, case_id, principal.tenant_id, "case")
    await session.delete(case)
    await session.commit()
    return envelope.ok({"ok": True})


@router.get("/cases/{case_id}/hearings")
async def list_hearings(
    case_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    principal: security.Principal = Depends(security.require_staff),
):
    await get_scoped_or_404(session, Case, case_id, principal.tenant_id, "case")
    rows = (
        await session.scalars(
            scoped(Hearing, principal.tenant_id)
            .where(Hearing.case_id == case_id)
            .order_by(Hearing.date.desc())
        )
    ).all()
    return envelope.ok(
        [HearingOut.model_validate(r).model_dump(mode="json") for r in rows]
    )


@router.post("/cases/{case_id}/hearings")
async def add_hearing(
    case_id: uuid.UUID,
    body: HearingCreate,
    session: AsyncSession = Depends(get_session),
    principal: security.Principal = Depends(security.require_staff),
):
    case = await get_scoped_or_404(session, Case, case_id, principal.tenant_id, "case")
    hearing = Hearing(
        tenant_id=principal.tenant_id,
        case_id=case_id,
        source="manual",
        **body.model_dump(),
    )
    session.add(hearing)

    # Keep the denormalised next_hearing_date honest: the case list and Today screen
    # sort on it, so a manually added future hearing must move it.
    is_sooner = case.next_hearing_date is None or body.date < case.next_hearing_date
    if is_sooner and body.date >= dt.date.today():
        case.next_hearing_date = body.date

    await session.commit()
    await session.refresh(hearing)
    return envelope.ok(HearingOut.model_validate(hearing).model_dump(mode="json"))


@router.patch("/hearings/{hearing_id}")
async def update_hearing(
    hearing_id: uuid.UUID,
    body: HearingUpdate,
    session: AsyncSession = Depends(get_session),
    principal: security.Principal = Depends(security.require_staff),
):
    hearing = await get_scoped_or_404(
        session, Hearing, hearing_id, principal.tenant_id, "hearing"
    )
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(hearing, field, value)
    await session.commit()
    await session.refresh(hearing)
    return envelope.ok(HearingOut.model_validate(hearing).model_dump(mode="json"))


@router.post("/cases/{case_id}/notes")
async def add_note(
    case_id: uuid.UUID,
    body: NoteCreate,
    session: AsyncSession = Depends(get_session),
    principal: security.Principal = Depends(security.require_staff),
):
    await get_scoped_or_404(session, Case, case_id, principal.tenant_id, "case")
    note = CaseNote(
        tenant_id=principal.tenant_id,
        case_id=case_id,
        author_id=principal.user_id,
        body=body.body,
    )
    session.add(note)
    await session.commit()
    await session.refresh(note)
    return envelope.ok(
        {"id": str(note.id), "body": note.body, "created_at": note.created_at.isoformat()}
    )


@router.get("/cases/{case_id}/timeline")
async def case_timeline(
    case_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    principal: security.Principal = Depends(security.require_staff),
):
    """B.6: hearings, documents and notes merged into one reverse-chronological feed."""
    await get_scoped_or_404(session, Case, case_id, principal.tenant_id, "case")
    events: list[TimelineEvent] = []

    hearings = (
        await session.scalars(
            scoped(Hearing, principal.tenant_id).where(Hearing.case_id == case_id)
        )
    ).all()
    for h in hearings:
        events.append(
            TimelineEvent(
                kind="hearing",
                # A hearing's position in the feed is its calendar day, rendered at
                # midnight IST rather than converted from an instant.
                at=dt.datetime.combine(h.date, h.time or dt.time.min, dt.UTC),
                title=h.purpose or "Hearing",
                detail=h.outcome_notes,
                ref_id=h.id,
            )
        )

    documents = (
        await session.scalars(
            scoped(Document, principal.tenant_id).where(Document.case_id == case_id)
        )
    ).all()
    for d in documents:
        events.append(
            TimelineEvent(kind="document", at=d.created_at, title=d.name, ref_id=d.id)
        )

    notes = (
        await session.scalars(
            scoped(CaseNote, principal.tenant_id).where(CaseNote.case_id == case_id)
        )
    ).all()
    for n in notes:
        events.append(
            TimelineEvent(kind="note", at=n.created_at, title="Note", detail=n.body, ref_id=n.id)
        )

    events.sort(key=lambda e: e.at, reverse=True)
    return envelope.ok([e.model_dump(mode="json") for e in events])


@router.post("/cases/{case_id}/sync")
async def sync_case(
    case_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    principal: security.Principal = Depends(security.require_staff),
):
    case = await get_scoped_or_404(session, Case, case_id, principal.tenant_id, "case")

    if not case.cnr:
        raise envelope.validation("This case was added manually and has no CNR to sync.")

    now = dt.datetime.now(dt.UTC)
    if case.last_synced_at is not None and now - case.last_synced_at < SYNC_COOLDOWN:
        remaining = int((SYNC_COOLDOWN - (now - case.last_synced_at)).total_seconds())
        # Reassurance, not an error report: the data is fresh, which is why the
        # refresh was skipped. Phrasing it as a failure makes a working app look broken
        # right after add-by-CNR, which syncs on creation.
        minutes = max(1, remaining // 60)
        raise envelope.rate_limited(
            f"Already up to date. You can refresh again in {minutes} minutes.", remaining
        )

    preview = await ecourts.lookup_cnr(case.cnr)
    case.court_name = preview.court_name or case.court_name
    case.judge_name = preview.judge_name or case.judge_name
    case.stage = preview.stage or case.stage
    case.next_hearing_date = preview.next_hearing_date or case.next_hearing_date
    case.ecourts_synced = True
    case.last_synced_at = now
    case.raw_ecourts = preview.model_dump(mode="json")

    await session.commit()
    await session.refresh(case)
    return envelope.ok(await _to_out(session, case))
