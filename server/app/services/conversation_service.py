"""Multi-turn research conversations (B.6).

Research is rarely one question. "What are the grounds for anticipatory bail?" is
followed by "and what about the appeal?", which retrieves nothing useful on its own —
the topic lives in the previous turn. `build_context_query` is what carries it forward.

Turns are stored as a JSONB list on the conversation rather than as rows, because they
are only ever read whole, and the assistant's half is a result object rather than a
string.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import envelope
from app.core.db import scoped
from app.models import AiConversation
from app.models.base import utcnow

# How many prior user turns fold into a follow-up's retrieval context. Small on
# purpose: a lawyer who has moved on to a different question is badly served by a
# search still weighted toward the one before it.
MAX_CONTEXT_TURNS = 3


async def create_conversation(
    session: AsyncSession, *, tenant_id: uuid.UUID, user_id: uuid.UUID, title: str
) -> AiConversation:
    conversation = AiConversation(
        tenant_id=tenant_id, user_id=user_id, title=title, messages=[]
    )
    session.add(conversation)
    await session.commit()
    await session.refresh(conversation)
    return conversation


async def get_for_user_or_404(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
) -> AiConversation:
    """Scoped to the user, not just the firm — same rule as `GET /ai/jobs`. Another
    lawyer's research thread is not this lawyer's business."""
    conversation = await session.scalar(
        scoped(AiConversation, tenant_id)
        .where(AiConversation.id == conversation_id)
        .where(AiConversation.user_id == user_id)
    )
    if conversation is None:
        raise envelope.not_found("conversation")
    return conversation


async def append_turn(
    session: AsyncSession, conversation: AiConversation, *, query: str, result: dict
) -> None:
    # Reassigned rather than appended in place: SQLAlchemy does not track mutations
    # inside a JSONB value, so an `.append()` here would commit nothing at all.
    now = utcnow().isoformat()
    conversation.messages = [
        *(conversation.messages or []),
        {"role": "user", "content": query, "at": now},
        {"role": "assistant", "content": result, "at": now},
    ]
    await session.commit()


def build_context_query(conversation: AiConversation, new_query: str) -> str:
    """Prefixes the new query with recent prior user turns, so a follow-up retrieves
    against the topic it is actually about."""
    prior_user_turns = [
        m["content"] for m in (conversation.messages or []) if m.get("role") == "user"
    ][-MAX_CONTEXT_TURNS:]

    if not prior_user_turns:
        return new_query

    return f"{' '.join(prior_user_turns)} {new_query}"
