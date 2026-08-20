from app.ai.fake_llm import fake_complete
from app.ai.prompts import build_classification_prompt, build_extraction_prompt


def test_classify_doc_type_chargesheet():
    system, user = build_classification_prompt(
        "The chargesheet was filed at the police station against the accused."
    )
    result = fake_complete(system=system, user=user)
    assert result == "chargesheet"


def test_classify_doc_type_judgment():
    system, user = build_classification_prompt(
        "The court held that the appeal is hereby ordered to be dismissed."
    )
    result = fake_complete(system=system, user=user)
    assert result == "judgment"


def test_classify_doc_type_agreement():
    system, user = build_classification_prompt(
        "This agreement is entered into between the party of the first part "
        "and the party of the second part."
    )
    result = fake_complete(system=system, user=user)
    assert result == "agreement"


def test_classify_doc_type_falls_back_to_other():
    system, user = build_classification_prompt("The weather today is sunny.")
    result = fake_complete(system=system, user=user)
    assert result == "other"


def test_extract_summary_returns_parseable_json_with_expected_keys():
    import json

    text = (
        "The accused was charged under Section 302 IPC on 12/03/2026. "
        "State vs Ramesh Kumar is the matter at hand."
    )
    system, user = build_extraction_prompt("chargesheet", text)
    raw = fake_complete(system=system, user=user)

    parsed = json.loads(raw)
    assert set(parsed.keys()) == {
        "summary_markdown",
        "key_points",
        "parties",
        "sections_invoked",
        "dates",
        "doc_type_detected",
    }
    assert "Section 302" in parsed["sections_invoked"]
    assert "12/03/2026" in parsed["dates"]


def test_fake_complete_unknown_task_returns_marked_fallback():
    result = fake_complete(system="TASK: some_future_task\ndo something", user="hello world")
    assert "FAKE LLM RESPONSE" in result
