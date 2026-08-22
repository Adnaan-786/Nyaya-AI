"""The C.9 draftsman, end to end and in its parts.

The property worth guarding: a field the caller did not supply is *reported*, never
invented. An invented date of arrest on a bail application is a far worse document than
an obviously incomplete one.
"""

import io

import pytest
from docx import Document
from httpx import AsyncClient

from app.core.envelope import ApiError
from app.services import draft_service
from tests.conftest import BASE, sign_in
from tests.test_ai import _await_job

pytestmark = pytest.mark.asyncio

VAKALATNAMA_FIELDS = {
    "court_name": "Bombay High Court",
    "case_number": "CIV/45/2026",
    "client_name": "Anita Rao",
    "advocate_name": "Adv. Vikram Shah",
    "bar_council_id": "MAH/1234/2020",
}


def test_an_unknown_template_is_rejected_before_any_work_happens() -> None:
    with pytest.raises(ApiError) as raised:
        draft_service.get_template_or_400("not_a_real_template")

    assert raised.value.code == "VALIDATION_ERROR"


def test_a_known_template_is_returned() -> None:
    assert draft_service.get_template_or_400("affidavit").id == "affidavit"


def test_optional_fields_are_not_reported_missing() -> None:
    template = draft_service.get_template_or_400("bail_application")
    fields = {
        "court_name": "x",
        "case_number": "x",
        "police_station": "x",
        "accused_name": "x",
        "sections_invoked": "x",
        "date_of_arrest": "2026-01-01",
        "grounds_for_bail": "x",
        # surety_details is optional on this template.
    }

    assert draft_service.compute_missing_fields(template, fields) == []


def test_a_whitespace_only_value_counts_as_missing() -> None:
    """Otherwise a form that submits empty strings reports a complete draft over a
    document with blanks in it."""
    template = draft_service.get_template_or_400("vakalatnama")

    missing = draft_service.compute_missing_fields(template, {**VAKALATNAMA_FIELDS, "client_name": "   "})

    assert missing == ["client_name"]


def test_case_data_fills_only_the_fields_the_caller_left_blank() -> None:
    class _Case:
        court_name = "Delhi High Court"
        case_number = "CIV/99/2026"
        cnr = None

    filled = draft_service._auto_fill_from_case(
        {"court_name": "Bombay High Court"}, _Case()
    )

    assert filled["court_name"] == "Bombay High Court"
    assert filled["case_number"] == "CIV/99/2026"


async def test_draft_returns_the_contract_shape_and_a_downloadable_docx(
    client: AsyncClient,
) -> None:
    headers = await sign_in(client, "Draft Firm")

    accepted = await client.post(
        f"{BASE}/ai/draft",
        headers=headers,
        json={"template_id": "vakalatnama", "fields": VAKALATNAMA_FIELDS},
    )
    assert accepted.status_code == 202

    job = await _await_job(client, headers, accepted.json()["data"]["job_id"])
    assert job["status"] == "done", job["error"]

    result = job["result"]
    assert set(result) == {"document_markdown", "docx_url", "document_id", "missing_fields"}
    assert result["missing_fields"] == []
    assert result["document_markdown"]

    downloaded = await client.get(result["docx_url"], headers=headers)
    assert downloaded.status_code == 200
    text = "\n".join(p.text for p in Document(io.BytesIO(downloaded.content)).paragraphs)
    # Built from the caller's own fields, so the client's name is genuinely in it.
    assert "Anita Rao" in text


async def test_a_draft_with_gaps_is_still_produced_and_says_what_is_missing(
    client: AsyncClient,
) -> None:
    """Refusing here would waste the whole job. The app deep-links from
    `missing_fields` so the lawyer can fill them in."""
    headers = await sign_in(client, "Partial Draft Firm")

    accepted = await client.post(
        f"{BASE}/ai/draft",
        headers=headers,
        json={"template_id": "vakalatnama", "fields": {"court_name": "Bombay High Court"}},
    )
    job = await _await_job(client, headers, accepted.json()["data"]["job_id"])

    assert job["status"] == "done", job["error"]
    assert "client_name" in job["result"]["missing_fields"]
    assert "advocate_name" in job["result"]["missing_fields"]
    assert job["result"]["document_markdown"]


async def test_a_case_supplies_the_court_and_case_number(client: AsyncClient) -> None:
    headers = await sign_in(client, "Case Draft Firm")
    case_id = (
        await client.post(
            f"{BASE}/cases",
            headers=headers,
            json={
                "title": "Ramesh v. State",
                "case_number": "CRL/22/2026",
                "court_name": "Sessions Court, Pune",
            },
        )
    ).json()["data"]["id"]

    accepted = await client.post(
        f"{BASE}/ai/draft",
        headers=headers,
        json={
            "template_id": "adjournment_application",
            "case_id": case_id,
            "fields": {"applicant_name": "Ramesh", "reason_for_adjournment": "Counsel unwell"},
        },
    )
    job = await _await_job(client, headers, accepted.json()["data"]["job_id"])

    assert job["status"] == "done", job["error"]
    # Neither was typed by the caller; both came out of the firm's own case record.
    assert job["result"]["missing_fields"] == []


async def test_the_draft_lands_in_the_firms_document_library(client: AsyncClient) -> None:
    """A draft is a document. Keeping it beside the ones it was drafted from is also
    what gives it tenant scoping and a signed download for free."""
    headers = await sign_in(client, "Library Draft Firm")

    accepted = await client.post(
        f"{BASE}/ai/draft",
        headers=headers,
        json={"template_id": "vakalatnama", "fields": VAKALATNAMA_FIELDS},
    )
    job = await _await_job(client, headers, accepted.json()["data"]["job_id"])

    listed = (await client.get(f"{BASE}/documents", headers=headers)).json()["data"]
    drafted = [d for d in listed if d["id"] == job["result"]["document_id"]]

    assert drafted, "the generated DOCX should appear in the document list"
    assert drafted[0]["folder"] == draft_service.DRAFTS_FOLDER


async def test_an_unknown_template_is_a_400_not_a_failed_job(client: AsyncClient) -> None:
    headers = await sign_in(client, "Bad Template Firm")

    response = await client.post(
        f"{BASE}/ai/draft", headers=headers, json={"template_id": "nope", "fields": {}}
    )

    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_another_firms_case_cannot_be_drafted_against(client: AsyncClient) -> None:
    a_headers = await sign_in(client, "Draft Firm A")
    b_headers = await sign_in(client, "Draft Firm B")
    case_id = (
        await client.post(
            f"{BASE}/cases", headers=a_headers, json={"title": "Confidential v. Matter"}
        )
    ).json()["data"]["id"]

    response = await client.post(
        f"{BASE}/ai/draft",
        headers=b_headers,
        json={"template_id": "vakalatnama", "case_id": case_id, "fields": {}},
    )

    assert response.json()["error"]["code"] == "CASE_NOT_FOUND"
