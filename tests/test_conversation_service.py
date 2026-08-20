from app.services.conversation_service import MAX_CONTEXT_TURNS, build_context_query


class _FakeConversation:
    def __init__(self, messages):
        self.messages = messages


def test_build_context_query_with_no_prior_turns_returns_query_unchanged():
    conversation = _FakeConversation(messages=[])
    result = build_context_query(conversation, "what are the grounds for bail")
    assert result == "what are the grounds for bail"


def test_build_context_query_prepends_prior_user_turns():
    conversation = _FakeConversation(
        messages=[
            {"role": "user", "content": "grounds for anticipatory bail", "at": "t1"},
            {"role": "assistant", "content": {"answer_markdown": "x"}, "at": "t1"},
        ]
    )
    result = build_context_query(conversation, "what about the appeal")
    assert "anticipatory bail" in result
    assert "what about the appeal" in result


def test_build_context_query_caps_to_max_context_turns():
    messages = []
    for i in range(10):
        messages.append({"role": "user", "content": f"query-{i}", "at": "t"})
        messages.append({"role": "assistant", "content": {}, "at": "t"})
    conversation = _FakeConversation(messages=messages)

    result = build_context_query(conversation, "final query")

    # Only the most recent MAX_CONTEXT_TURNS user turns should appear.
    for i in range(10 - MAX_CONTEXT_TURNS):
        assert f"query-{i}" not in result
    for i in range(10 - MAX_CONTEXT_TURNS, 10):
        assert f"query-{i}" in result
