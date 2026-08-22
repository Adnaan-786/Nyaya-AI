"""The `fake` provider's task dispatch.

FAKE_MODE is what the demo runs on and what the whole AI suite runs against, so a
schema drift here is a schema drift everywhere — these assert that each prompt's
`TASK:` tag reaches the right fabricator and comes back parseable.
"""

import json

from app.ai.fake_llm import fake_complete
from app.ai.prompts import (
    build_classification_prompt,
    build_draft_prompt,
    build_extraction_prompt,
    build_risk_clause_prompt,
)


def _classify(text: str) -> str:
    system, user = build_classification_prompt(text)
    return fake_complete(system=system, user=user)


def test_a_chargesheet_is_recognised() -> None:
    assert (
        _classify("The chargesheet was filed at the police station against the accused.")
        == "chargesheet"
    )


def test_a_judgment_is_recognised() -> None:
    assert _classify("The court held that the appeal is hereby ordered to be dismissed.") == (
        "judgment"
    )


def test_an_agreement_is_recognised() -> None:
    assert (
        _classify(
            "This agreement is entered into between the party of the first part "
            "and the party of the second part."
        )
        == "agreement"
    )


def test_an_unrecognisable_document_falls_back_to_other() -> None:
    assert _classify("The weather today is sunny.") == "other"


def test_extraction_returns_json_with_exactly_the_contract_keys() -> None:
    text = (
        "The accused was charged under Section 302 IPC on 12/03/2026. "
        "State vs Ramesh Kumar is the matter at hand."
    )
    system, user = build_extraction_prompt("chargesheet", text)

    parsed = json.loads(fake_complete(system=system, user=user))

    assert set(parsed) == {
        "summary_markdown",
        "key_points",
        "parties",
        "sections_invoked",
        "dates",
        "doc_type_detected",
    }
    # Derived from the real input rather than canned, so the demo reflects the actual
    # upload instead of contradicting what is on screen.
    assert "Section 302" in parsed["sections_invoked"]
    assert "12/03/2026" in parsed["dates"]


def test_a_risk_assessment_is_json_with_a_valid_severity() -> None:
    system, user = build_risk_clause_prompt("The Vendor shall indemnify the Client.")

    parsed = json.loads(fake_complete(system=system, user=user))

    assert parsed["severity"] in ("high", "medium", "low")
    assert parsed["explanation"]


def test_a_draft_is_built_only_from_the_fields_it_was_given() -> None:
    system, user = build_draft_prompt(
        template_id="vakalatnama",
        template_name="Vakalatnama",
        instructions="Draft a vakalatnama.",
        fields={"client_name": "Anita Rao", "advocate_name": "Adv. Vikram Shah"},
    )

    markdown = fake_complete(system=system, user=user)

    assert "Anita Rao" in markdown
    assert "Adv. Vikram Shah" in markdown


def test_an_unknown_task_returns_something_visibly_fake() -> None:
    """A future task must not silently produce output that reads as a real answer in
    a screenshot."""
    result = fake_complete(system="TASK: some_future_task\ndo something", user="hello world")

    assert "FAKE LLM RESPONSE" in result
