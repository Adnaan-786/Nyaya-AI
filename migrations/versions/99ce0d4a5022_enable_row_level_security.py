"""enable row level security

Revision ID: 99ce0d4a5022
Revises: 3cd60e567a95
Create Date: 2026-07-27 15:36:26.827448
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "99ce0d4a5022"
down_revision: Union[str, Sequence[str], None] = "3cd60e567a95"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TENANT_TABLES = [
    "users",
    "clients",
    "cases",
    "hearings",
    "documents",
    "doc_chunks",
    "ai_jobs",
    "ai_conversations",
    "invoices",
    "payments",
    "time_entries",
    "expenses",
    "tasks",
    "notifications",
    "audit_logs",
]


def upgrade() -> None:
    """Enable PostgreSQL Row-Level Security."""

    for table in TENANT_TABLES:
        op.execute(
            f"""
            ALTER TABLE {table}
            ENABLE ROW LEVEL SECURITY;
            """
        )

        op.execute(
            f"""
            CREATE POLICY {table}_tenant_policy
            ON {table}
            USING (
                tenant_id =
                current_setting('app.tenant_id')::uuid
            );
            """
        )


def downgrade() -> None:
    """Disable PostgreSQL Row-Level Security."""

    for table in TENANT_TABLES:
        op.execute(
            f"""
            DROP POLICY IF EXISTS
            {table}_tenant_policy
            ON {table};
            USING (
            tenant_id = current_setting('app.tenant_id')::uuid
            );
            """
        )

        op.execute(
            f"""
            ALTER TABLE {table}
            DISABLE ROW LEVEL SECURITY;
            """
        )