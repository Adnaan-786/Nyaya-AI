"""B.6 universal search: cases, clients and documents, grouped with highlights."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import envelope, security
from app.core.db import get_session, scoped
from app.models import Case, Client, Document
from app.schemas.documents import SearchHit, SearchResults

router = APIRouter(tags=["search"])

PER_GROUP = 10
HIGHLIGHT_WINDOW = 60


def _highlight(text: str | None, query: str) -> str | None:
    """A snippet centred on the match.

    Returning the whole OCR text would be megabytes; returning nothing would leave the
    user guessing why a 40-page chargesheet matched. The window is the answer.
    """
    if not text:
        return None

    position = text.lower().find(query.lower())
    if position < 0:
        return None

    start = max(0, position - HIGHLIGHT_WINDOW)
    end = min(len(text), position + len(query) + HIGHLIGHT_WINDOW)
    snippet = " ".join(text[start:end].split())
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(text) else ""
    return f"{prefix}{snippet}{suffix}"


@router.get("/search")
async def search(
    q: str = Query(..., min_length=2),
    type: str = Query("all", pattern="^(all|cases|clients|documents)$"),
    session: AsyncSession = Depends(get_session),
    principal: security.Principal = Depends(security.require_staff),
):
    term = q.strip()
    pattern = f"%{term}%"
    results = SearchResults()

    if type in ("all", "cases"):
        rows = (
            await session.scalars(
                scoped(Case, principal.tenant_id)
                .where(
                    or_(
                        Case.title.ilike(pattern),
                        Case.cnr.ilike(pattern),
                        Case.case_number.ilike(pattern),
                        Case.court_name.ilike(pattern),
                    )
                )
                .order_by(Case.next_hearing_date.asc().nulls_last())
                .limit(PER_GROUP)
            )
        ).all()
        results.cases = [
            SearchHit(id=c.id, title=c.title, subtitle=c.court_name, highlight=c.cnr)
            for c in rows
        ]

    if type in ("all", "clients"):
        rows = (
            await session.scalars(
                scoped(Client, principal.tenant_id)
                .where(
                    or_(
                        Client.name.ilike(pattern),
                        Client.phone.ilike(pattern),
                        Client.email.ilike(pattern),
                    )
                )
                .order_by(Client.name)
                .limit(PER_GROUP)
            )
        ).all()
        results.clients = [
            SearchHit(id=c.id, title=c.name, subtitle=c.phone) for c in rows
        ]

    if type in ("all", "documents"):
        rows = (
            await session.scalars(
                scoped(Document, principal.tenant_id)
                .where(
                    Document.confirmed.is_(True),
                    # Searching the extracted text is the point — that is what makes a
                    # scanned chargesheet findable by a phrase inside it, not just by
                    # whatever the file happened to be named.
                    or_(Document.name.ilike(pattern), Document.ocr_text.ilike(pattern)),
                )
                .order_by(Document.created_at.desc())
                .limit(PER_GROUP)
            )
        ).all()
        results.documents = [
            SearchHit(
                id=d.id,
                title=d.name,
                subtitle=d.folder,
                highlight=_highlight(d.ocr_text, term),
            )
            for d in rows
        ]

    return envelope.ok(results.model_dump(mode="json"))
