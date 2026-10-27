"""
DPDP data-principal rights (plan C.12.2): export and erasure.

Scope decisions (flagged for legal review in the README):

  EXPORT  is the user's *own* data -- profile, consents, devices (never
          push tokens), notification settings and history, tasks,
          time entries, assigned cases, document *metadata*, AI job
          history, and the audit trail of their own actions. It does not
          bulk-export firm/client matter data or document contents:
          those belong to the firm and its clients and are subject to
          privilege.

  ERASURE removes/anonymises the user's personal data but keeps the
          firm's records intact. Documents the user uploaded are deleted
          *unless* they sit on a case that is open or under legal hold
          (litigation duty), in which case they are retained and
          reported in the request summary.
"""

import io
import json
import uuid
import zipfile
from datetime import timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DuplicateResourceException, ValidationException
from app.core.logging import get_logger
from app.core.security import utcnow
from app.db.enums import CaseStatus
from app.db.tenant import TenantContext
from app.integrations import storage
from app.models.ai_job import AIJob
from app.models.audit_log import AuditLog
from app.models.case import Case
from app.models.case_assignee import CaseAssignee
from app.models.client import Client
from app.models.consent import Consent
from app.models.data_request import DataRequest
from app.models.device import Device
from app.models.doc_chunk import DocChunk
from app.models.document import Document
from app.models.notification import Notification
from app.models.notification_settings import NotificationSettings
from app.models.otp_request import OTPRequest
from app.models.refresh_token import RefreshToken
from app.models.task import Task
from app.models.time_entry import TimeEntry
from app.models.user import User

logger = get_logger(__name__)

EXPORT_LINK_DAYS = 7  # also the SigV4 presigned-URL maximum
DELETE_WINDOW_DAYS = 30

EXPORT_README = (
    "NyayaAI personal data export\n\n"
    "This archive contains the personal data we hold about YOU: your profile, consents, "
    "devices, notification settings and history, tasks and time entries assigned to you, "
    "the cases you are assigned to, metadata of documents you uploaded, your AI job "
    "history, and the audit trail of your own actions.\n\n"
    "It does not contain your firm's or its clients' matter data or the contents of "
    "documents: those are held on behalf of the firm and its clients and may be "
    "privileged. Ask your firm administrator if you need them.\n"
)


def build_export_zip(files: dict[str, Any]) -> bytes:
    """Pure: {filename: json-serialisable} -> ZIP bytes (+ a README)."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("README.txt", EXPORT_README)
        for name, content in files.items():
            archive.writestr(f"{name}.json", json.dumps(content, indent=2, default=str, ensure_ascii=False))
    return buffer.getvalue()


def is_document_retained(*, case_status: str | None, case_legal_hold: bool | None) -> bool:
    """Pure retention rule: a document on an open case or a case under legal hold is kept."""
    if case_status is None:  # not attached to any case
        return False
    return bool(case_legal_hold) or case_status == CaseStatus.OPEN.value


# ------------------------------------------------------------------ requests


async def _pending(session: AsyncSession, user_id: UUID, kind: str) -> DataRequest | None:
    return (
        await session.execute(
            select(DataRequest)
            .where(DataRequest.user_id == user_id)
            .where(DataRequest.kind == kind)
            .where(DataRequest.status.in_(["pending", "processing"]))
        )
    ).scalars().first()


async def create_export_request(session: AsyncSession, tenant: TenantContext) -> DataRequest:
    existing = await _pending(session, tenant.user_id, "export")
    if existing is not None:
        return existing  # idempotent: don't queue a second export while one is running
    request = DataRequest(tenant_id=tenant.tenant_id, user_id=tenant.user_id, kind="export", status="pending", summary={})
    session.add(request)
    await session.commit()
    await session.refresh(request)
    return request


async def create_delete_request(session: AsyncSession, tenant: TenantContext) -> DataRequest:
    if await _pending(session, tenant.user_id, "delete") is not None:
        raise DuplicateResourceException("A deletion request is already pending for this account.")
    request = DataRequest(
        tenant_id=tenant.tenant_id,
        user_id=tenant.user_id,
        kind="delete",
        status="pending",
        scheduled_for=utcnow() + timedelta(days=DELETE_WINDOW_DAYS),
        summary={},
    )
    session.add(request)
    await session.commit()
    await session.refresh(request)
    return request


async def cancel_delete_request(session: AsyncSession, tenant: TenantContext) -> DataRequest:
    request = await _pending(session, tenant.user_id, "delete")
    if request is None or request.status != "pending":
        raise ValidationException("There is no cancellable deletion request.")
    request.status = "cancelled"
    request.completed_at = utcnow()
    await session.commit()
    await session.refresh(request)
    return request


async def get_request_or_404(session: AsyncSession, tenant: TenantContext, request_id: UUID) -> DataRequest:
    request = (
        await session.execute(
            select(DataRequest)
            .where(DataRequest.id == request_id)
            .where(DataRequest.user_id == tenant.user_id)  # a user only sees their own requests
        )
    ).scalar_one_or_none()
    if request is None:
        raise ValidationException("Request not found.")
    return request


async def list_requests(session: AsyncSession, tenant: TenantContext) -> list[DataRequest]:
    rows = await session.execute(
        select(DataRequest).where(DataRequest.user_id == tenant.user_id).order_by(DataRequest.created_at.desc())
    )
    return list(rows.scalars().all())


def export_download_url(request: DataRequest) -> str | None:
    if request.kind != "export" or request.status != "completed" or not request.result_key or not request.expires_at:
        return None
    remaining = int((request.expires_at - utcnow()).total_seconds())
    if remaining <= 0:
        return None
    return storage.generate_presigned_download_url(
        request.result_key, filename="nyayaai-data-export.zip", expires_in=min(remaining, EXPORT_LINK_DAYS * 86400)
    )


# -------------------------------------------------------------------- export


async def collect_user_data(session: AsyncSession, user_id: UUID) -> dict[str, Any]:
    user = (await session.execute(select(User).where(User.id == user_id))).scalar_one()

    async def rows(stmt):
        return list((await session.execute(stmt)).scalars().all())

    consents = await rows(select(Consent).where(Consent.user_id == user_id))
    devices = await rows(select(Device).where(Device.user_id == user_id))
    settings_row = (
        await session.execute(select(NotificationSettings).where(NotificationSettings.user_id == user_id))
    ).scalar_one_or_none()
    notifications = await rows(select(Notification).where(Notification.user_id == user_id))
    tasks = await rows(select(Task).where(Task.assigned_to == user_id))
    entries = await rows(select(TimeEntry).where(TimeEntry.user_id == user_id))
    cases = await rows(select(Case).join(CaseAssignee, CaseAssignee.case_id == Case.id).where(CaseAssignee.user_id == user_id))
    documents = await rows(select(Document).where(Document.uploaded_by == user_id))
    jobs = await rows(select(AIJob).where(AIJob.user_id == user_id))
    audit = await rows(select(AuditLog).where(AuditLog.actor_id == user_id).order_by(AuditLog.at.desc()).limit(10000))

    return {
        "profile": {
            "id": user.id, "name": user.name, "phone": user.phone, "email": user.email,
            "role": user.role, "language": user.language, "bar_council_id": user.bar_council_id,
            "created_at": user.created_at,
        },
        "consents": [{"version": c.version, "granted_at": c.granted_at, "text_hash": c.text_hash} for c in consents],
        # push tokens are credentials, not personal data to hand back
        "devices": [{"platform": d.platform, "app_version": d.app_version, "last_seen": d.updated_at} for d in devices],
        "notification_settings": None if settings_row is None else {
            "digest_time": settings_row.digest_time, "push_enabled": settings_row.push_enabled,
            "whatsapp_enabled": settings_row.whatsapp_enabled, "sms_enabled": settings_row.sms_enabled,
        },
        "notifications": [{"type": str(n.type), "payload": n.payload, "read_at": n.read_at, "created_at": n.created_at} for n in notifications],
        "tasks": [{"title": t.title, "status": str(t.status), "due_date": t.due_date, "case_id": t.case_id} for t in tasks],
        "time_entries": [{"case_id": e.case_id, "date": e.date, "duration_minutes": e.duration_minutes, "description": e.description} for e in entries],
        "assigned_cases": [{"id": c.id, "title": c.title, "status": str(c.status)} for c in cases],
        "uploaded_documents": [{"name": d.name, "mime_type": d.mime_type, "size_bytes": d.size_bytes, "case_id": d.case_id, "uploaded_at": d.created_at} for d in documents],
        "ai_jobs": [{"type": j.type, "status": str(j.status), "created_at": j.created_at} for j in jobs],
        "audit_trail": [{"action": a.action, "entity_type": a.entity_type, "entity_id": a.entity_id, "ip": a.ip, "at": a.at} for a in audit],
    }


async def run_export(session: AsyncSession, request: DataRequest) -> None:
    """Builds the ZIP, uploads it, and records the 7-day expiry. `session` must be tenant-scoped."""
    request.status = "processing"
    await session.commit()

    data = await collect_user_data(session, request.user_id)
    key = f"tenants/{request.tenant_id}/exports/{request.id}.zip"
    storage.put_object_bytes(key, build_export_zip(data), content_type="application/zip")

    request.result_key = key
    request.expires_at = utcnow() + timedelta(days=EXPORT_LINK_DAYS)
    request.status = "completed"
    request.completed_at = utcnow()
    request.summary = {k: (len(v) if isinstance(v, list) else 1 if v else 0) for k, v in data.items()}
    await session.commit()


# --------------------------------------------------------------- hard delete


async def run_hard_delete(session: AsyncSession, request: DataRequest) -> dict[str, int]:
    """
    Executes an erasure request whose 30-day window has elapsed.
    `session` must be tenant-scoped. Returns the (counts-only) summary.
    """
    request.status = "processing"
    await session.commit()

    user = (await session.execute(select(User).where(User.id == request.user_id))).scalar_one()
    summary = {"documents_deleted": 0, "documents_retained_legal": 0, "s3_delete_failures": 0}

    docs = (await session.execute(select(Document, Case).outerjoin(Case, Case.id == Document.case_id).where(Document.uploaded_by == user.id))).all()
    for document, case in docs:
        status = None if case is None else (case.status.value if hasattr(case.status, "value") else case.status)
        if is_document_retained(case_status=status, case_legal_hold=None if case is None else case.legal_hold):
            summary["documents_retained_legal"] += 1
            continue
        if document.s3_key:
            try:
                storage.delete_object(document.s3_key)
            except Exception as exc:  # noqa: BLE001 - keep going; report it
                summary["s3_delete_failures"] += 1
                logger.error("dpdp_s3_delete_failed", document_id=str(document.id), error=str(exc))
        await session.execute(delete(DocChunk).where(DocChunk.document_id == document.id))
        await session.delete(document)
        summary["documents_deleted"] += 1

    phone = user.phone
    await session.execute(delete(Device).where(Device.user_id == user.id))
    await session.execute(delete(RefreshToken).where(RefreshToken.user_id == user.id))
    await session.execute(delete(NotificationSettings).where(NotificationSettings.user_id == user.id))
    await session.execute(delete(Notification).where(Notification.user_id == user.id))
    await session.execute(delete(OTPRequest).where(OTPRequest.phone == phone))

    # A client-portal user is also a data principal in the firm's client list.
    await session.execute(
        update(Client).where(Client.user_id == user.id).values(
            name="Deleted client", phone=None, email=None, address=None, tags=None, user_id=None
        )
    )

    # Anonymise rather than drop the row: firm records (tasks, time
    # entries, audit rows) keep a valid, non-identifying reference.
    user.name = "Deleted user"
    user.phone = f"del-{uuid.uuid4().hex[:12]}"
    user.email = None
    user.bar_council_id = None

    request.status = "completed"
    request.completed_at = utcnow()
    request.summary = summary
    session.add(
        AuditLog(
            tenant_id=request.tenant_id, actor_id=None, action="dpdp.hard_delete",
            entity_type="users", entity_id=str(user.id), ip=None, user_agent=None,
        )
    )
    await session.commit()
    return summary
