import uuid

from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.enums import OCRStatus
from app.db.mixins import TenantMixin, TimestampMixin, UUIDMixin


class Document(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "documents"

    case_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    client_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    folder: Mapped[str | None] = mapped_column(
        String(255),
    )

    mime_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    size_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    s3_key: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    ocr_status: Mapped[OCRStatus] = mapped_column(
        default=OCRStatus.PENDING,
        nullable=False,
    )

    # Raw extracted text (OCR output or native text extraction for
    # DOCX/plain text). This is what gets chunked+embedded (M6) and
    # summarized (M7); it is never returned directly over the API.
    extracted_text: Mapped[str | None] = mapped_column(
        nullable=True,
    )

    ocr_error: Mapped[str | None] = mapped_column(
        nullable=True,
    )

    # Full-text search vector, populated from extracted_text via
    # to_tsvector() (see app/services/document_service.py) -- never
    # assigned a plain Python string directly, since asyncpg has no
    # str -> tsvector adapter.
    ocr_text: Mapped[str | None] = mapped_column(
        TSVECTOR, nullable=True,
    )

    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"),
    )

    tenant = relationship("Tenant", back_populates="documents")
    case = relationship("Case", back_populates="documents")
    client = relationship("Client")
    uploader = relationship("User")
    chunks = relationship(
        "DocChunk",
        back_populates="document",
        cascade="all, delete-orphan",
    )