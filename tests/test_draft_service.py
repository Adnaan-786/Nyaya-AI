import uuid

import pytest

from app.core.exceptions import ValidationException
from app.db.tenant import TenantContext
from app.services import draft_service


@pytest.fixture(autouse=True)
def _mock_storage(monkeypatch):
    """
    draft_document() calls out to S3/MinIO to upload the generated
    DOCX; these tests exercise the drafting logic itself (field
    validation, prompt building, markdown generation) without needing
    a live object store, same as how the route/service layer tests
    elsewhere in this suite avoid a live Postgres.
    """
    uploaded = {}

    def fake_put_object_bytes(key, data, *, content_type):
        uploaded["key"] = key
        uploaded["data"] = data
        uploaded["content_type"] = content_type

    def fake_generate_presigned_download_url(key, *, filename=None):
        return f"https://fake-storage.local/{key}"

    monkeypatch.setattr(
        "app.integrations.storage.put_object_bytes", fake_put_object_bytes
    )
    monkeypatch.setattr(
        "app.integrations.storage.generate_presigned_download_url",
        fake_generate_presigned_download_url,
    )
    return uploaded


def _tenant() -> TenantContext:
    return TenantContext(tenant_id=uuid.uuid4(), user_id=uuid.uuid4())


def test_get_template_or_404_raises_for_unknown_template():
    with pytest.raises(ValidationException):
        draft_service.get_template_or_404("not_a_real_template")


def test_get_template_or_404_returns_template_for_known_id():
    template = draft_service.get_template_or_404("affidavit")
    assert template.id == "affidavit"


@pytest.mark.asyncio
async def test_draft_document_returns_contract_shape(_mock_storage):
    result = await draft_service.draft_document(
        tenant=_tenant(),
        job_id=uuid.uuid4(),
        template_id="vakalatnama",
        case=None,
        fields={
            "court_name": "Bombay High Court",
            "case_number": "CIV/45/2026",
            "client_name": "Anita Rao",
            "advocate_name": "Adv. Vikram Shah",
            "bar_council_id": "MAH/1234/2020",
        },
        language="en",
    )

    assert set(result.keys()) == {"document_markdown", "docx_url", "missing_fields"}
    assert result["missing_fields"] == []
    assert result["docx_url"].startswith("https://fake-storage.local/")
    assert result["document_markdown"]


@pytest.mark.asyncio
async def test_draft_document_reports_missing_required_fields(_mock_storage):
    result = await draft_service.draft_document(
        tenant=_tenant(),
        job_id=uuid.uuid4(),
        template_id="vakalatnama",
        case=None,
        fields={"court_name": "Bombay High Court"},
        language="en",
    )

    assert "client_name" in result["missing_fields"]
    assert "advocate_name" in result["missing_fields"]
    # Still produces a best-effort draft even with missing fields --
    # never silently refuses, per contract's "app can deep-link to fix".
    assert result["document_markdown"]


@pytest.mark.asyncio
async def test_draft_document_auto_fills_from_case(_mock_storage):
    class FakeCase:
        court_name = "Delhi High Court"
        case_number = "CIV/99/2026"
        cnr = None

    result = await draft_service.draft_document(
        tenant=_tenant(),
        job_id=uuid.uuid4(),
        template_id="adjournment_application",
        case=FakeCase(),
        fields={"applicant_name": "Ramesh", "reason_for_adjournment": "Counsel unwell"},
        language="en",
    )

    # court_name/case_number weren't in the caller's fields but should
    # be auto-filled from the case, so they shouldn't show as missing.
    assert "court_name" not in result["missing_fields"]
    assert "case_number" not in result["missing_fields"]


def test_compute_missing_fields_ignores_optional_fields():
    template = draft_service.get_template_or_404("bail_application")
    # surety_details is optional on this template
    fields = {
        "court_name": "x",
        "case_number": "x",
        "police_station": "x",
        "accused_name": "x",
        "sections_invoked": "x",
        "date_of_arrest": "2026-01-01",
        "grounds_for_bail": "x",
    }
    missing = draft_service.compute_missing_fields(template, fields)
    assert missing == []
