"""Multi-turn research: carrying the topic into a follow-up, and who may read it."""

import pytest
from httpx import AsyncClient

from app.services.conversation_service import MAX_CONTEXT_TURNS, build_context_query
from tests.conftest import BASE, sign_in
from tests.test_ai import _await_job

pytestmark = pytest.mark.asyncio


class _Conversation:
    """Stands in for the model row — `build_context_query` only reads `messages`."""

    def __init__(self, messages: list) -> None:
        self.messages = messages


def test_a_first_question_is_left_exactly_as_asked() -> None:
    assert (
        build_context_query(_Conversation([]), "what are the grounds for bail")
        == "what are the grounds for bail"
    )


def test_a_follow_up_carries_the_earlier_topic() -> None:
    """"What about the appeal?" retrieves nothing on its own — the subject of the
    question is in the turn before it."""
    conversation = _Conversation(
        [
            {"role": "user", "content": "grounds for anticipatory bail", "at": "t1"},
            {"role": "assistant", "content": {"answer_markdown": "x"}, "at": "t1"},
        ]
    )

    result = build_context_query(conversation, "what about the appeal")

    assert "anticipatory bail" in result
    assert "what about the appeal" in result


def test_only_the_assistant_turns_are_left_out() -> None:
    conversation = _Conversation(
        [
            {"role": "user", "content": "section 138 limitation", "at": "t"},
            {"role": "assistant", "content": {"answer_markdown": "SECRET"}, "at": "t"},
        ]
    )

    result = build_context_query(conversation, "and interim compensation")

    assert "SECRET" not in result


def test_old_turns_stop_diluting_the_current_question() -> None:
    messages = []
    for i in range(10):
        messages.append({"role": "user", "content": f"query-{i}", "at": "t"})
        messages.append({"role": "assistant", "content": {}, "at": "t"})

    result = build_context_query(_Conversation(messages), "final query")

    for i in range(10 - MAX_CONTEXT_TURNS):
        assert f"query-{i}" not in result
    for i in range(10 - MAX_CONTEXT_TURNS, 10):
        assert f"query-{i}" in result


async def test_a_conversation_records_the_answer_it_was_given(client: AsyncClient) -> None:
    headers = await sign_in(client, "Thread Firm")
    created = await client.post(
        f"{BASE}/ai/conversations", headers=headers, json={"title": "Cheque bounce"}
    )
    conversation_id = created.json()["data"]["id"]

    accepted = await client.post(
        f"{BASE}/ai/research",
        headers=headers,
        json={"query": "Section 138 limitation period", "conversation_id": conversation_id},
    )
    assert accepted.status_code == 202
    await _await_job(client, headers, accepted.json()["data"]["job_id"])

    conversation = (
        await client.get(f"{BASE}/ai/conversations/{conversation_id}", headers=headers)
    ).json()["data"]

    assert conversation["title"] == "Cheque bounce"
    assert [m["role"] for m in conversation["messages"]] == ["user", "assistant"]
    assert conversation["messages"][0]["content"] == "Section 138 limitation period"
    assert "confidence" in conversation["messages"][1]["content"]


async def test_another_firm_cannot_read_the_thread(client: AsyncClient) -> None:
    a_headers = await sign_in(client, "Thread Firm A")
    b_headers = await sign_in(client, "Thread Firm B")

    created = await client.post(f"{BASE}/ai/conversations", headers=a_headers, json={})
    conversation_id = created.json()["data"]["id"]

    denied = await client.get(f"{BASE}/ai/conversations/{conversation_id}", headers=b_headers)

    assert denied.json()["error"]["code"] == "CONVERSATION_NOT_FOUND"


async def test_research_against_another_firms_conversation_is_refused(
    client: AsyncClient,
) -> None:
    a_headers = await sign_in(client, "Thread Firm C")
    b_headers = await sign_in(client, "Thread Firm D")

    created = await client.post(f"{BASE}/ai/conversations", headers=a_headers, json={})
    conversation_id = created.json()["data"]["id"]

    response = await client.post(
        f"{BASE}/ai/research",
        headers=b_headers,
        json={"query": "confidential strategy", "conversation_id": conversation_id},
    )

    assert response.json()["error"]["code"] == "CONVERSATION_NOT_FOUND"
