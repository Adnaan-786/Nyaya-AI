from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationException
from app.core.security import utcnow
from app.db.tenant import TenantContext
from app.models.ai_conversation import AIConversation

# How many prior user turns to fold into a follow-up query's retrieval
# context (plan C.9: "follow-ups re-run retrieval with conversation
# context"). Kept small so old turns don't dilute the current question.
MAX_CONTEXT_TURNS = 3


async def get_or_create_conversation(
    session: AsyncSession,
    tenant: TenantContext,
    *,
    user_id: UUID,
    conversation_id: UUID | None,
) -> AIConversation:
    if conversation_id is not None:
        result = await session.execute(
            select(AIConversation)
            .where(AIConversation.id == conversation_id)
            .where(AIConversation.tenant_id == tenant.tenant_id)
        )
        conversation = result.scalar_one_or_none()
        if conversation is None:
            raise ValidationException("Conversation not found.")
        return conversation

    conversation = AIConversation(tenant_id=tenant.tenant_id, user_id=user_id, messages=[])
    session.add(conversation)
    await session.commit()
    await session.refresh(conversation)
    return conversation


async def get_conversation_or_404(
    session: AsyncSession, tenant: TenantContext, conversation_id: UUID
) -> AIConversation:
    result = await session.execute(
        select(AIConversation)
        .where(AIConversation.id == conversation_id)
        .where(AIConversation.tenant_id == tenant.tenant_id)
    )
    conversation = result.scalar_one_or_none()
    if conversation is None:
        raise ValidationException("Conversation not found.")
    return conversation


async def append_turn(
    session: AsyncSession,
    conversation: AIConversation,
    *,
    query: str,
    result: dict,
) -> None:
    messages = list(conversation.messages or [])
    now = utcnow().isoformat()
    messages.append({"role": "user", "content": query, "at": now})
    messages.append({"role": "assistant", "content": result, "at": now})
    conversation.messages = messages
    await session.commit()


def build_context_query(conversation: AIConversation, new_query: str) -> str:
    """
    Prefixes the new query with recent prior user turns so a follow-up
    like "what about the appeal?" retrieves against the right topic.
    """
    prior_user_turns = [
        m["content"] for m in (conversation.messages or []) if m.get("role") == "user"
    ][-MAX_CONTEXT_TURNS:]

    if not prior_user_turns:
        return new_query

    context = " ".join(prior_user_turns)
    return f"{context} {new_query}"
