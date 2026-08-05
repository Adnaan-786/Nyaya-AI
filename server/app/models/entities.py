"""Core tables from C.4, typed to match the contract models in B.5.

Two conventions are load-bearing and are the same ones the Android client enforces:

* **Money is integer paise** (`BigInteger`), never numeric/float. Rs. 1,500.50 == 150050.
* **Calendar dates are `Date`, not `DateTime`.** `hearings.date`,
  `cases.next_hearing_date` and `invoices.due_date` are days on a cause list, not
  instants. Storing them as timestamps is what makes a hearing show up on the wrong
  day in any timezone behind UTC.


The datetime import is qualified for the same reason as in the schemas: the columns
genuinely named `date` and `time` would otherwise shadow the same-named types, and a
shadowed annotation makes SQLAlchemy miss `Optional` and emit NOT NULL — which is how
an optional hearing time becomes a required one.
"""

import datetime as dt
import uuid

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantScoped, Timestamped, UuidPk


class User(UuidPk, TenantScoped, Timestamped, Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("phone", name="uq_users_phone"),)

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # Nullable since the email OTP channel landed: an account created by email has no
    # phone until its owner adds one. Phone stays the primary identity wherever it
    # exists — client portal invites are still keyed on it — but it is no longer the
    # only way to own an account. Postgres permits many NULLs under a UNIQUE
    # constraint, so uq_users_phone keeps working unchanged.
    phone: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(255))
    # firm_admin | lawyer | intern | client (B.4)
    role: Mapped[str] = mapped_column(String(30), nullable=False, default="lawyer")
    language: Mapped[str] = mapped_column(String(5), nullable=False, default="en")
    bar_council_id: Mapped[str | None] = mapped_column(String(100))
    # Set for role=client: the client record this login is scoped to (B.4 roles).
    client_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("clients.id", ondelete="SET NULL")
    )
    # Team-management "remove member" (DELETE /users/{id}) sets this False instead of
    # deleting the row. A hard delete would CASCADE through time_entries, ai_jobs,
    # ai_conversations, devices and notifications (ondelete="CASCADE" on their
    # user_id FKs) — wiping a departed lawyer's billing history out from under the
    # firm's invoices. Deactivating preserves every FK (tasks.assignee_id/created_by,
    # case_notes.author_id keep resolving; time entries stay attached to their case)
    # while removing the user from active team listings and (future) login.
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Client(UuidPk, TenantScoped, Timestamped, Base):
    __tablename__ = "clients"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255))
    address: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)


class Case(UuidPk, TenantScoped, Timestamped, Base):
    __tablename__ = "cases"
    __table_args__ = (
        # C.4: `cnr UNIQUE NULLS DISTINCT` — manual cases have no CNR and must not
        # collide with each other.
        UniqueConstraint("tenant_id", "cnr", name="uq_cases_tenant_cnr"),
    )

    cnr: Mapped[str | None] = mapped_column(String(16), index=True)
    title: Mapped[str] = mapped_column(String(400), nullable=False)
    case_number: Mapped[str | None] = mapped_column(String(100))
    court_name: Mapped[str | None] = mapped_column(String(300))
    court_type: Mapped[str | None] = mapped_column(String(100))
    judge_name: Mapped[str | None] = mapped_column(String(200))
    case_type: Mapped[str | None] = mapped_column(String(100))
    stage: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(30), default="active", nullable=False)
    client_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("clients.id", ondelete="SET NULL")
    )
    # Calendar date. Never a timestamp — see the module docstring.
    next_hearing_date: Mapped[dt.date | None] = mapped_column(Date)
    ecourts_synced: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_synced_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    raw_ecourts: Mapped[dict | None] = mapped_column(JSONB)


class CaseAssignee(Base):
    __tablename__ = "case_assignees"

    case_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )


class Hearing(UuidPk, TenantScoped, Timestamped, Base):
    __tablename__ = "hearings"

    case_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False
    )
    date: Mapped[dt.date] = mapped_column(Date, nullable=False, index=True)
    time: Mapped[dt.time | None] = mapped_column(Time)
    purpose: Mapped[str | None] = mapped_column(String(300))
    courtroom: Mapped[str | None] = mapped_column(String(120))
    outcome_notes: Mapped[str | None] = mapped_column(Text)
    # ecourts | manual (B.5)
    source: Mapped[str] = mapped_column(String(20), default="manual", nullable=False)


class Document(UuidPk, TenantScoped, Timestamped, Base):
    __tablename__ = "documents"

    case_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE")
    )
    client_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("clients.id", ondelete="SET NULL")
    )
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    folder: Mapped[str | None] = mapped_column(String(120))
    mime_type: Mapped[str] = mapped_column(String(120), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    # pending | done | failed (B.5)
    ocr_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    ocr_text: Mapped[str | None] = mapped_column(Text)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    # True once the client has PUT the bytes and called /confirm (B.9).
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class AiJob(UuidPk, TenantScoped, Timestamped, Base):
    __tablename__ = "ai_jobs"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # summarize | research | draft | risk_review (B.5)
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    # queued | running | done | failed (B.5)
    status: Mapped[str] = mapped_column(String(20), default="queued", nullable=False)
    input: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    result: Mapped[dict | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)
    estimated_seconds: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    completed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True))


class AiConversation(UuidPk, TenantScoped, Timestamped, Base):
    __tablename__ = "ai_conversations"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(300), default="Research", nullable=False)
    messages: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)


class Invoice(UuidPk, TenantScoped, Timestamped, Base):
    __tablename__ = "invoices"
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="uq_invoices_tenant_number"),
    )

    client_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False
    )
    case_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("cases.id", ondelete="SET NULL")
    )
    number: Mapped[str] = mapped_column(String(50), nullable=False)
    line_items: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    # All money is integer paise (B.1.5).
    subtotal_paise: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    gst_rate: Mapped[int] = mapped_column(Integer, default=18, nullable=False)
    gst_paise: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    total_paise: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    # draft | sent | paid | overdue (B.5)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    due_date: Mapped[dt.date | None] = mapped_column(Date)
    pdf_key: Mapped[str | None] = mapped_column(String(500))
    payment_link: Mapped[str | None] = mapped_column(String(500))


class Payment(UuidPk, TenantScoped, Timestamped, Base):
    __tablename__ = "payments"

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False
    )
    razorpay_order_id: Mapped[str | None] = mapped_column(String(100), index=True)
    razorpay_payment_id: Mapped[str | None] = mapped_column(String(100))
    amount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="created", nullable=False)
    # B.10: an invoice is only marked paid once the server verifies the signature
    # AND the webhook lands. The app never decides this from its SDK result.
    verified_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))


class TimeEntry(UuidPk, TenantScoped, Timestamped, Base):
    __tablename__ = "time_entries"

    case_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    started_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    billable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    rate_paise: Mapped[int | None] = mapped_column(BigInteger)
    # Set when pulled into an invoice, so "import unbilled time" cannot double-bill.
    invoiced_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))


class Expense(UuidPk, TenantScoped, Timestamped, Base):
    __tablename__ = "expenses"

    case_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("cases.id", ondelete="SET NULL")
    )
    description: Mapped[str] = mapped_column(String(300), nullable=False)
    amount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    category: Mapped[str | None] = mapped_column(String(80))
    receipt_document_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True))
    incurred_on: Mapped[dt.date | None] = mapped_column(Date)


class Task(UuidPk, TenantScoped, Timestamped, Base):
    __tablename__ = "tasks"

    case_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE")
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    due_date: Mapped[dt.date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="open", nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )


class CaseNote(UuidPk, TenantScoped, Timestamped, Base):
    __tablename__ = "case_notes"

    case_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False
    )
    author_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)


class Notification(UuidPk, TenantScoped, Timestamped, Base):
    __tablename__ = "notifications"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # B.8 push types.
    type: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    deep_link: Mapped[str | None] = mapped_column(String(200))
    payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    read_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))


class Device(UuidPk, TenantScoped, Timestamped, Base):
    __tablename__ = "devices"
    __table_args__ = (UniqueConstraint("fcm_token", name="uq_devices_token"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    fcm_token: Mapped[str] = mapped_column(String(500), nullable=False)
    platform: Mapped[str] = mapped_column(String(20), default="android", nullable=False)
    app_version: Mapped[str | None] = mapped_column(String(40))


class OtpCode(UuidPk, Timestamped, Base):
    """Not tenant-scoped: at OTP time we do not yet know the tenant."""

    __tablename__ = "otp_codes"

    # Holds whatever the code was sent to — a phone number or an email address. The
    # column keeps its original name so no live table has to be renamed; 255 is the
    # email cap, widened from the 20 that only ever had to fit a phone.
    identifier: Mapped[str] = mapped_column(
        "phone", String(255), nullable=False, index=True
    )
    code_hash: Mapped[str] = mapped_column(String(200), nullable=False)
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class RefreshToken(UuidPk, Timestamped, Base):
    __tablename__ = "refresh_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # B.4.4: rotation — the old token is invalidated the moment a new pair is issued.
    revoked_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))


# Full-text search over extracted document text (C.4 `ocr_text tsvector-indexed`).
Index(
    "ix_documents_ocr_text_fts",
    Document.ocr_text,
    postgresql_using="gin",
    postgresql_ops={"ocr_text": "gin_trgm_ops"},
)
Index("ix_cases_next_hearing", Case.tenant_id, Case.next_hearing_date)
Index("ix_hearings_tenant_date", Hearing.tenant_id, Hearing.date)
