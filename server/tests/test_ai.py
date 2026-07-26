"""B.7 async job pattern, and the safety properties of the AI surface."""

import asyncio

import pytest
from httpx import AsyncClient

from app.api import ai
from tests.conftest import BASE, sign_in
from tests.test_documents import CHARGESHEET, _upload

pytestmark = pytest.mark.asyncio


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
