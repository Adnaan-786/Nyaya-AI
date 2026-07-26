"""Importing this package registers every table on the shared metadata.

Without this, `Base.metadata.create_all` (and Alembic autogenerate) sees only the
tables whose modules happen to have been imported already — which silently produces
a one-table database.
"""

from app.models.base import Base, Tenant, TenantScoped, Timestamped, UuidPk, new_id, utcnow
from app.models.entities import (
    AiConversation,
    AiJob,
    Case,
    CaseAssignee,
    CaseNote,
    Client,
    Device,
    Document,
    Expense,
    Hearing,
    Invoice,
    Notification,
    OtpCode,
    Payment,
    RefreshToken,
    Task,
    TimeEntry,
    User,
)

__all__ = [
    "AiConversation",
    "AiJob",
    "Base",
    "Case",
    "CaseAssignee",
    "CaseNote",
    "Client",
    "Device",
    "Document",
    "Expense",
    "Hearing",
    "Invoice",
    "Notification",
    "OtpCode",
    "Payment",
    "RefreshToken",
    "Task",
    "Tenant",
    "TenantScoped",
    "TimeEntry",
    "Timestamped",
    "User",
    "UuidPk",
    "new_id",
    "utcnow",
]
