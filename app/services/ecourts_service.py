from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import (
    CaseNotFoundException,
    RateLimitException,
    UpstreamUnavailableException,
)
from app.core.security import utcnow
from app.db.enums import NotificationType
from app.db.tenant import TenantContext
from app.integrations.ecourts import ECourtsProviderError, NormalizedCase, get_ecourts_provider
from app.models.case import Case
from app.models.case_assignee import CaseAssignee
from app.models.ecourts_lookup_cache import ECourtsLookupCache
from app.services import notification_service
from app.services.case_service import validate_cnr

settings = get_settings()


def _normalized_to_dict(normalized: NormalizedCase) -> dict:
    return {
        "cnr": normalized.cnr,
        "title": normalized.title,
        "court_name": normalized.court_name,
        "court_type": normalized.court_type,
        "judge_name": normalized.judge_name,
        "case_type": normalized.case_type,
        "stage": normalized.stage,
        "parties": normalized.parties,
        "next_hearing_date": (
            normalized.next_hearing_date.isoformat() if normalized.next_hearing_date else None
        ),
        "history": [
            {
                "date": h.date.isoformat(),
                "purpose": h.purpose,
                "outcome_notes": h.outcome_notes,
            }
            for h in normalized.history
        ],
        "raw": normalized.raw,
    }


def _dict_to_normalized(payload: dict) -> NormalizedCase:
    import datetime

    from app.integrations.ecourts import NormalizedHearing

    return NormalizedCase(
        cnr=payload["cnr"],
        title=payload["title"],
        court_name=payload.get("court_name"),
        court_type=payload.get("court_type"),
        judge_name=payload.get("judge_name"),
        case_type=payload.get("case_type"),
        stage=payload.get("stage"),
        parties=payload.get("parties", []),
        next_hearing_date=(
            datetime.date.fromisoformat(payload["next_hearing_date"])
            if payload.get("next_hearing_date")
            else None
        ),
        history=[
            NormalizedHearing(
                date=datetime.date.fromisoformat(h["date"]),
                purpose=h.get("purpose"),
                outcome_notes=h.get("outcome_notes"),
            )
            for h in payload.get("history", [])
        ],
        raw=payload.get("raw", {}),
    )


async def lookup_cnr(session: AsyncSession, cnr: str, *, use_cache: bool = True) -> NormalizedCase:
    """
    POST /cases/lookup-cnr: synchronous provider call with a 24h cache
    (contract B.6/C.7). Not tenant-scoped -- the same CNR returns the
    same public court data for every firm.
    """
    validate_cnr(cnr)

    now = utcnow()

    if use_cache:
        result = await session.execute(
            select(ECourtsLookupCache).where(ECourtsLookupCache.cnr == cnr)
        )
        cached = result.scalar_one_or_none()
        if cached is not None:
            age_hours = (now - cached.fetched_at).total_seconds() / 3600
            if age_hours < settings.ecourts_lookup_cache_hours:
                return _dict_to_normalized(cached.payload)

    provider = get_ecourts_provider()

    try:
        normalized = await provider.lookup_cnr(cnr)
    except ECourtsProviderError as exc:
        raise UpstreamUnavailableException(
            message="eCourts data source is currently unavailable.",
            details={"cnr": cnr},
        ) from exc

    payload = _normalized_to_dict(normalized)

    result = await session.execute(
        select(ECourtsLookupCache).where(ECourtsLookupCache.cnr == cnr)
    )
    cache_row = result.scalar_one_or_none()

    if cache_row is None:
        session.add(ECourtsLookupCache(cnr=cnr, payload=payload, fetched_at=now))
    else:
        cache_row.payload = payload
        cache_row.fetched_at = now

    await session.commit()

    return normalized


async def create_case_from_cnr(
    session: AsyncSession,
    tenant: TenantContext,
    *,
    cnr: str,
    client_id: UUID,
) -> Case:
    """POST /cases/from-cnr (contract B.6)."""
    normalized = await lookup_cnr(session, cnr)

    case = Case(
        tenant_id=tenant.tenant_id,
        cnr=normalized.cnr,
        title=normalized.title,
        court_name=normalized.court_name,
        court_type=normalized.court_type,
        judge_name=normalized.judge_name,
        case_type=normalized.case_type,
        stage=normalized.stage,
        client_id=client_id,
        next_hearing_date=normalized.next_hearing_date,
        ecourts_synced=True,
        last_synced_at=utcnow(),
        raw_ecourts=_normalized_to_dict(normalized),
    )
    session.add(case)
    await session.commit()
    await session.refresh(case)

    return case


async def sync_case(session: AsyncSession, tenant: TenantContext, case: Case) -> Case:
    """
    Force-refreshes one synced case (contract B.6 `POST /cases/{id}/sync`,
    rate-limited 1/hour/case). See `_apply_sync` for the diff/notify
    logic shared with the scheduled polling worker.
    """
    if not case.cnr:
        raise CaseNotFoundException(
            message="Case is not linked to a CNR; nothing to sync."
        )

    now = utcnow()
    if case.last_synced_at is not None:
        elapsed_hours = (now - case.last_synced_at).total_seconds() / 3600
        if elapsed_hours < (1.0 / settings.ecourts_sync_rate_limit_per_hour):
            raise RateLimitException(
                "This case was synced recently; please try again later.",
                details={"retry_after_seconds": int(3600 - elapsed_hours * 3600)},
            )

    return await _apply_sync(session, tenant, case)


async def _apply_sync(session: AsyncSession, tenant: TenantContext, case: Case) -> Case:
    """
    Fetches the latest status for `case`, diffs it against the last
    known state, persists changes, and notifies assignees (plan C.7
    points 3-4). Shared by the manual `/cases/{id}/sync` route and the
    scheduled polling worker (`app/workers/ecourts_worker.py`) -- the
    only difference between the two callers is *when* this runs, not
    what it does.
    """
    now = utcnow()
    provider = get_ecourts_provider()

    try:
        normalized = await provider.case_status(case.cnr)
    except ECourtsProviderError as exc:
        case.sync_failure_count += 1
        await session.commit()
        if case.sync_failure_count >= settings.ecourts_max_consecutive_failures:
            # Plan C.7: "alert if a case fails 3 consecutive days" --
            # the actual paging/Slack hook is wired up in M12's
            # observability stack; this is the signal it consumes.
            from app.core.logging import get_logger

            get_logger(__name__).warning(
                "ecourts_sync_repeated_failure",
                case_id=str(case.id),
                cnr=case.cnr,
                failures=case.sync_failure_count,
            )
        raise UpstreamUnavailableException(
            message="eCourts data source is currently unavailable.",
            details={"cnr": case.cnr},
        ) from exc

    changed_fields: dict[str, tuple] = {}

    if normalized.stage != case.stage:
        changed_fields["stage"] = (case.stage, normalized.stage)
        case.stage = normalized.stage

    if normalized.next_hearing_date != case.next_hearing_date:
        changed_fields["next_hearing_date"] = (
            case.next_hearing_date,
            normalized.next_hearing_date,
        )
        case.next_hearing_date = normalized.next_hearing_date

    previous_history_len = len((case.raw_ecourts or {}).get("history", []))
    new_history_len = len(normalized.history)
    order_added = new_history_len > previous_history_len

    case.raw_ecourts = _normalized_to_dict(normalized)
    case.last_synced_at = now
    case.sync_failure_count = 0

    await session.commit()
    await session.refresh(case)

    if changed_fields or order_added:
        result = await session.execute(
            select(CaseAssignee.user_id).where(CaseAssignee.case_id == case.id)
        )
        assignee_ids = [row[0] for row in result.all()]

        change_summary = ", ".join(
            f"{field} changed" for field in changed_fields
        ) or "a new order/hearing entry was found"

        for user_id in assignee_ids:
            await notification_service.notify_user(
                session,
                tenant_id=tenant.tenant_id,
                user_id=user_id,
                type=NotificationType.CASE_UPDATE,
                payload={
                    "case_id": str(case.id),
                    "change_summary": change_summary,
                },
            )
        await session.commit()

    return case
