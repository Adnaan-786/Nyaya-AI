"""B.7 async job pattern, and the safety properties of the AI surface."""

import asyncio

import pytest
from httpx import AsyncClient

from app.api import ai
from app.integrations.llm import _drop_unverifiable_citations
from app.schemas.ai import Citation, ResearchResult
from tests.conftest import BASE, sign_in
from tests.test_documents import CHARGESHEET, _pdf, _upload

pytestmark = pytest.mark.asyncio


def _citation(source_url: str) -> Citation:
    return Citation(
        case_title="Some vs Body",
        court="Supreme Court of India",
        year="2020",
        source_url=source_url,
        relevance_note="On point.",
    )


def test_citations_without_a_real_url_are_dropped_and_confidence_downgraded() -> None:
    """The prompt asks the model not to fabricate a URL, but this is the actual
    guarantee — a blank source_url is exactly the failure mode a live call
    produced the first time this integration went live, and it must never reach
    the app looking like a confident, verifiable answer."""
    result = ResearchResult(
        answer_markdown="The limitation period is one month.",
        citations=[_citation(""), _citation("https://indiankanoon.org/doc/123/")],
        confidence="high",
    )

    cleaned = _drop_unverifiable_citations(result)

    assert len(cleaned.citations) == 1
    assert cleaned.citations[0].source_url == "https://indiankanoon.org/doc/123/"
    # One real citation survives, so confidence is left as the model reported it —
    # only a *complete* wipeout forces a downgrade.
    assert cleaned.confidence == "high"


def test_confidence_is_forced_to_insufficient_when_every_citation_is_unverifiable() -> None:
    result = ResearchResult(
        answer_markdown="Some confident-sounding claim.",
        citations=[_citation(""), _citation("not-a-url")],
        confidence="high",
    )

    cleaned = _drop_unverifiable_citations(result)

    assert cleaned.citations == []
    assert cleaned.confidence == "insufficient"


def test_already_clean_results_pass_through_unchanged() -> None:
    result = ResearchResult(
        answer_markdown="x",
        citations=[_citation("https://indiankanoon.org/doc/456/")],
        confidence="medium",
    )

    cleaned = _drop_unverifiable_citations(result)

    assert cleaned is result


async def _await_job(http: AsyncClient, headers: dict, job_id: str) -> dict:
    """Poll as the app does. Background tasks run after the response is sent, so a
    single immediate read would race them."""
    for _ in range(50):
        job = (await http.get(f"{BASE}/ai/jobs/{job_id}", headers=headers)).json()["data"]
        if job["status"] in ("done", "failed"):
            return job
        await asyncio.sleep(0.05)
    raise AssertionError(f"job {job_id} never finished")


async def test_summarize_returns_202_then_completes(client: AsyncClient) -> None:
    headers = await sign_in(client, "AI Firm")
    document_id = await _upload(client, headers, "Chargesheet.pdf", CHARGESHEET)

    accepted = await client.post(
        f"{BASE}/ai/summarize",
        headers=headers,
        json={"document_id": document_id, "doc_type_hint": "chargesheet"},
    )

    # B.7: 202 immediately with exactly these three fields.
    assert accepted.status_code == 202
    data = accepted.json()["data"]
    assert data["status"] == "queued"
    assert data["estimated_seconds"] > 0

    job = await _await_job(client, headers, data["job_id"])
    assert job["status"] == "done"

    # The result shape is the contract the app decodes.
    result = job["result"]
    for field in (
        "summary_markdown",
        "key_points",
        "parties",
        "sections_invoked",
        "dates",
        "doc_type_detected",
    ):
        assert field in result, f"missing contract field {field}"

    # Extraction actually fed the summarizer — this section only exists inside the PDF.
    assert "Section 138" in result["sections_invoked"]


async def test_job_poll_response_keeps_estimated_seconds_and_input_ref(
    client: AsyncClient,
) -> None:
    """`AiJobOut` (the `GET /ai/jobs/{id}` shape the app polls) fixes `estimated_seconds`
    and `input_ref`. A looser job schema that dropped either — as a `dict[str, Any]`
    result shape would — breaks the app's spinner estimate and its poll contract."""
    headers = await sign_in(client, "Contract Firm")

    accepted = await client.post(
        f"{BASE}/ai/research", headers=headers, json={"query": "contract field regression"}
    )
    job = await _await_job(client, headers, accepted.json()["data"]["job_id"])

    assert "estimated_seconds" in job
    assert job["estimated_seconds"] > 0
    assert "input_ref" in job


async def test_research_never_fabricates_citations_without_a_provider(
    client: AsyncClient,
) -> None:
    """The single most dangerous failure this product could have.

    With no API key configured, the researcher must return `insufficient` and an
    empty citation list. A plausible-looking fake citation would eventually be
    carried into a courtroom.
    """
    headers = await sign_in(client, "Research Firm")

    accepted = await client.post(
        f"{BASE}/ai/research",
        headers=headers,
        json={"query": "Interim compensation under Section 138 NI Act", "language": "en"},
    )
    job = await _await_job(client, headers, accepted.json()["data"]["job_id"])

    assert job["status"] == "done"
    assert job["result"]["confidence"] == "insufficient"
    assert job["result"]["citations"] == []
    # B.7: an insufficient answer still explains itself rather than rendering blank.
    assert job["result"]["answer_markdown"].strip()


async def test_hinglish_query_is_accepted(client: AsyncClient) -> None:
    """D.8 encourages Hinglish input — it must not be rejected as malformed."""
    headers = await sign_in(client, "Hinglish Firm")

    accepted = await client.post(
        f"{BASE}/ai/research",
        headers=headers,
        json={"query": "Section 138 mein interim compensation kab milta hai?", "language": "hi"},
    )

    assert accepted.status_code == 202


async def test_summarize_without_extracted_text_fails_fast(client: AsyncClient) -> None:
    """Queueing a job that is certain to fail would show a 45-second spinner and
    then an error; rejecting up front lets the app say what is actually wrong."""
    headers = await sign_in(client, "NoText Firm")
    issued = (
        await client.post(
            f"{BASE}/documents/upload-url",
            headers=headers,
            json={"name": "x.pdf", "mime_type": "application/pdf", "size_bytes": 10},
        )
    ).json()["data"]

    response = await client.post(
        f"{BASE}/ai/summarize", headers=headers, json={"document_id": issued["document_id"]}
    )

    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_quota_exceeded_carries_paywall_details(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """B.14: every 402 must carry limit, plan and upgrade_to so the app opens the
    paywall with the right plan preselected."""
    monkeypatch.setitem(ai.DAILY_JOB_LIMITS, "solo", 1)
    headers = await sign_in(client, "Quota Firm")

    first = await client.post(
        f"{BASE}/ai/research", headers=headers, json={"query": "first question"}
    )
    assert first.status_code == 202

    second = await client.post(
        f"{BASE}/ai/research", headers=headers, json={"query": "second question"}
    )

    assert second.status_code == 402
    error = second.json()["error"]
    assert error["code"] == "QUOTA_EXCEEDED"
    assert error["details"]["limit"] == "1"
    assert error["details"]["upgrade_to"] == "firm"


async def test_jobs_are_scoped_to_the_requesting_user(client: AsyncClient) -> None:
    """Research history is personal — another firm must not see it, and the list is
    scoped to the user rather than the whole firm."""
    a_headers = await sign_in(client, "Job Firm A")
    b_headers = await sign_in(client, "Job Firm B")

    accepted = await client.post(
        f"{BASE}/ai/research", headers=a_headers, json={"query": "confidential strategy"}
    )
    job_id = accepted.json()["data"]["job_id"]

    denied = await client.get(f"{BASE}/ai/jobs/{job_id}", headers=b_headers)
    assert denied.json()["error"]["code"] == "JOB_NOT_FOUND"

    listed = (await client.get(f"{BASE}/ai/jobs", headers=b_headers)).json()
    assert listed["meta"]["total"] == 0


CONTRACT = _pdf(
    [
        "SERVICE AGREEMENT",
        "1. The Vendor shall indemnify and hold harmless the Client from all claims.",
        "2. Payment shall be made within 15 days of invoice.",
    ]
)


async def test_risk_review_returns_a_row_per_clause(client: AsyncClient) -> None:
    """D.8 renders the result as a list a lawyer works down, so each row must carry its
    own severity, its own clause text, and something to do about it."""
    headers = await sign_in(client, "Risk Firm")
    document_id = await _upload(client, headers, "Agreement.pdf", CONTRACT)

    accepted = await client.post(
        f"{BASE}/ai/risk-review", headers=headers, json={"document_id": document_id}
    )
    assert accepted.status_code == 202

    job = await _await_job(client, headers, accepted.json()["data"]["job_id"])
    assert job["status"] == "done", job["error"]

    risks = job["result"]["risks"]
    assert risks
    for risk in risks:
        assert set(risk) == {"severity", "clause_text", "explanation", "suggestion"}
        assert risk["severity"] in ("high", "medium", "low")


async def test_risk_review_without_extracted_text_fails_fast(client: AsyncClient) -> None:
    headers = await sign_in(client, "Risk NoText Firm")
    issued = (
        await client.post(
            f"{BASE}/documents/upload-url",
            headers=headers,
            json={"name": "x.pdf", "mime_type": "application/pdf", "size_bytes": 10},
        )
    ).json()["data"]

    response = await client.post(
        f"{BASE}/ai/risk-review", headers=headers, json={"document_id": issued["document_id"]}
    )

    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_another_firms_document_cannot_be_risk_reviewed(client: AsyncClient) -> None:
    a_headers = await sign_in(client, "Risk Firm A")
    b_headers = await sign_in(client, "Risk Firm B")
    document_id = await _upload(client, a_headers, "Agreement.pdf", CONTRACT)

    response = await client.post(
        f"{BASE}/ai/risk-review", headers=b_headers, json={"document_id": document_id}
    )

    assert response.json()["error"]["code"] == "DOCUMENT_NOT_FOUND"


async def test_the_template_catalogue_is_what_the_drafting_form_needs(
    client: AsyncClient,
) -> None:
    headers = await sign_in(client, "Template Firm")

    templates = (await client.get(f"{BASE}/ai/templates", headers=headers)).json()["data"]

    assert templates
    for template in templates:
        assert set(template) == {"id", "name", "category", "fields"}
        assert template["fields"], template["id"]
        for field in template["fields"]:
            assert field["type"] in ("string", "date", "number", "text")


async def test_the_new_job_types_are_listable_by_type(client: AsyncClient) -> None:
    """D.8's "Recent AI results" filter has to know about draft and risk_review too,
    or the hub silently hides half the history."""
    headers = await sign_in(client, "Job Filter Firm")
    await client.post(
        f"{BASE}/ai/draft",
        headers=headers,
        json={"template_id": "affidavit", "fields": {"deponent_name": "Anita Rao"}},
    )

    listed = (await client.get(f"{BASE}/ai/jobs?type=draft", headers=headers)).json()

    assert listed["meta"]["total"] == 1
    assert listed["data"][0]["type"] == "draft"
