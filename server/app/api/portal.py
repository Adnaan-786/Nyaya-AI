"""Client mode (D.10) — the app shell a `role=client` login sees.

The design rule here is **allow-list, not filter**. Portal responses are built from
explicitly chosen fields rather than by taking a staff response and removing things:
a staff serializer that gains a field later would silently leak it to clients, while
an allow-list simply doesn't carry it.

What a client must never see, no matter how they ask: AI job output, the document
vault, internal case notes, time entries, team members, or any other client's data.
Every route below scopes to `user.client_id`, and the plan's own words apply — the
server enforces this, the app merely also hides it.
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Page, paginate
from app.core import envelope, security
from app.core.db import get_session
from app.core.india import today_in_india
from app.models import Case, Hearing, Invoice, User

router = APIRouter(prefix="/portal", tags=["portal"])

# Plain language, no legalese (D.10). The internal stage strings are court shorthand
# that means nothing to a client — "Evidence" tells them more than "EVIDENCE_PW1".
FRIENDLY_STATUS = {
    "active": "In progress",
    "disposed": "Closed",
    "on_hold": "On hold",
}


async def portal_client_id(
    session: AsyncSession = Depends(get_session),
    principal: security.Principal = Depends(security.current_principal),
) -> uuid.UUID:
    """The single gate. Every portal route depends on this."""
    if not principal.is_client:
        raise envelope.forbidden_role("This area is for clients.")

    user = await session.get(User, principal.user_id)
    if user is None or user.client_id is None:
        # A client login with no linked client record can see nothing at all —
        # failing closed rather than falling back to the whole firm.
        raise envelope.forbidden_role("This login is not linked to a client record.")
    return user.client_id


def _case_summary(case: Case) -> dict:
    return {
        "id": str(case.id),
        "title": case.title,
        "case_number": case.case_number,
        "court_name": case.court_name,
        "status": FRIENDLY_STATUS.get(case.status, case.status),
        "next_hearing_date": (
            case.next_hearing_date.isoformat() if case.next_hearing_date else None
        ),
    }


@router.get("/cases")
async def portal_cases(
    page: Page = Depends(),
    session: AsyncSession = Depends(get_session),
    principal: security.Principal = Depends(security.current_principal),
    client_id: uuid.UUID = Depends(portal_client_id),
):
    statement = (
        select(Case)
        .where(Case.tenant_id == principal.tenant_id, Case.client_id == client_id)
        .order_by(Case.next_hearing_date.asc().nullslast(), Case.created_at.desc())
    )
    rows, meta = await paginate(session, statement, page)
    return envelope.ok([_case_summary(case) for case in rows], meta)


@router.get("/cases/{case_id}")
async def portal_case_detail(
    case_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    principal: security.Principal = Depends(security.current_principal),
    client_id: uuid.UUID = Depends(portal_client_id),
):
    """Case detail plus a sanitized hearing timeline.

    `outcome_notes` is deliberately excluded: those are the lawyer's working notes on
    what happened in court, written for the file and not for the client to read raw.
    """
    case = await session.get(Case, case_id)
    if case is None or case.tenant_id != principal.tenant_id or case.client_id != client_id:
        raise envelope.not_found("case")

    hearings = (
        await session.scalars(
            select(Hearing)
            .where(Hearing.case_id == case.id, Hearing.tenant_id == principal.tenant_id)
            .order_by(Hearing.date.desc())
        )
    ).all()

    today = today_in_india()
    detail = _case_summary(case)
    detail["judge_name"] = case.judge_name
    detail["timeline"] = [
        {
            "id": str(hearing.id),
            "date": hearing.date.isoformat(),
            "time": hearing.time.isoformat() if hearing.time else None,
            "purpose": hearing.purpose,
            "is_upcoming": hearing.date >= today,
        }
        for hearing in hearings
    ]
    return envelope.ok(detail)


@router.get("/invoices")
async def portal_invoices(
    page: Page = Depends(),
    session: AsyncSession = Depends(get_session),
    principal: security.Principal = Depends(security.current_principal),
    client_id: uuid.UUID = Depends(portal_client_id),
):
    """Only invoices that have been sent.

    A draft invoice is the lawyer still deciding what to charge; showing it to the
    client turns every edit into an awkward conversation.
    """
    statement = (
        select(Invoice)
        .where(
            Invoice.tenant_id == principal.tenant_id,
            Invoice.client_id == client_id,
            Invoice.status != "draft",
        )
        .order_by(Invoice.created_at.desc())
    )
    rows, meta = await paginate(session, statement, page)

    return envelope.ok(
        [
            {
                "id": str(invoice.id),
                "number": invoice.number,
                "total_paise": invoice.total_paise,
                "status": invoice.status,
                "due_date": invoice.due_date.isoformat() if invoice.due_date else None,
                "pdf_url": f"/v1/invoices/{invoice.id}/pdf",
                "payment_link": invoice.payment_link,
                "created_at": invoice.created_at.isoformat(),
            }
            for invoice in rows
        ],
        meta,
    )
