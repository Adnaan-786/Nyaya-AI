from uuid import UUID

from app.ai import docx_generator
from app.ai.prompts import build_draft_prompt
from app.ai.templates import Template, get_template
from app.core.exceptions import ValidationException
from app.core.logging import get_logger
from app.db.tenant import TenantContext
from app.integrations import storage
from app.integrations.llm import complete

logger = get_logger(__name__)


def _auto_fill_from_case(fields: dict, case) -> dict:
    """
    Fills a handful of common fields from real case data when the
    caller didn't already supply them -- this is drawing on data
    already in the tenant's own database, not inventing anything
    (plan C.9: "never invented facts").
    """
    filled = dict(fields)
    case_derived = {
        "court_name": case.court_name,
        "case_number": case.case_number or case.cnr,
    }
    for key, value in case_derived.items():
        if not filled.get(key) and value:
            filled[key] = value
    return filled


def compute_missing_fields(template: Template, fields: dict) -> list[str]:
    return [
        f.name
        for f in template.fields
        if f.required and not str(fields.get(f.name, "")).strip()
    ]


def get_template_or_404(template_id: str) -> Template:
    template = get_template(template_id)
    if template is None:
        raise ValidationException(
            "Unknown template_id.",
            details={"template_id": template_id},
        )
    return template


async def draft_document(
    *,
    tenant: TenantContext,
    job_id: UUID,
    template_id: str,
    case,
    fields: dict,
    language: str = "en",
) -> dict:
    """
    Returns the AIJob.result shape for type="draft" (contract B.7):
    document_markdown, docx_url, missing_fields[].
    """
    template = get_template_or_404(template_id)

    effective_fields = dict(fields)
    if case is not None:
        effective_fields = _auto_fill_from_case(effective_fields, case)

    missing_fields = compute_missing_fields(template, effective_fields)

    system, user = build_draft_prompt(
        template_id=template.id,
        template_name=template.name,
        instructions=template.instructions,
        fields=effective_fields,
        language=language,
    )
    document_markdown = await complete(system=system, user=user)

    docx_bytes = docx_generator.markdown_to_docx_bytes(document_markdown)

    key = f"tenants/{tenant.tenant_id}/ai_drafts/{job_id}.docx"
    storage.put_object_bytes(
        key,
        docx_bytes,
        content_type=(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
    )
    docx_url = storage.generate_presigned_download_url(
        key, filename=f"{template.id}.docx"
    )

    return {
        "document_markdown": document_markdown,
        "docx_url": docx_url,
        "missing_fields": missing_fields,
    }
