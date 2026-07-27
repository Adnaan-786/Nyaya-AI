"""add search indexes

Revision ID: aa7202907aac
Revises: 99ce0d4a5022
Create Date: 2026-07-27 18:05:00.985232

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'aa7202907aac'
down_revision: Union[str, Sequence[str], None] = '99ce0d4a5022'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # Convert VARCHAR -> TSVECTOR
    op.execute("""
        ALTER TABLE documents
        ALTER COLUMN ocr_text
        TYPE tsvector
        USING to_tsvector('english', coalesce(ocr_text, ''));
    """)

    # Full-text search index
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_documents_ocr_text
        ON documents
        USING GIN (ocr_text);
    """)

    # Vector index
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_doc_chunks_embedding
        ON doc_chunks
        USING hnsw (embedding vector_cosine_ops);
    """)

def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_doc_chunks_embedding")
    op.execute("DROP INDEX IF EXISTS ix_documents_ocr_text")

    op.execute("""
        ALTER TABLE documents
        ALTER COLUMN ocr_text
        TYPE VARCHAR
        USING ocr_text::text;
    """)