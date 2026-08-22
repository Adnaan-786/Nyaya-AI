"""The C.9 draftsman: fill a template's prose from the caller's fields, return a DOCX.

Two rules make this safe to put in front of a lawyer:

* **Facts come from fields, never from the model.** The prompt forbids inventing names,
  dates and amounts, and anything the template requires but the caller did not supply
  comes back in `missing_fields` for the app to deep-link to. A blank is reported, not
  filled in with something plausible — an invented date of arrest on a bail application
  is worse than an obviously incomplete one.
* **A missing field never blocks the draft.** The lawyer still gets the document with
  the gaps marked, because a refusal at this point wastes the whole job.

The DOCX lands in the firm's own document library rather than in some parallel store:
a draft is a document, it belongs beside the ones it was drafted from, and it inherits
the signed-download route and tenant scoping documents already have.
"""

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import docx_generator
from app.ai.prompts import build_draft_prompt
from app.ai.templates import Template, get_template
from app.core import envelope
from app.integrations import storage
from app.integrations.llm import complete
from app.models import Case, Document

logger = logging.getLogger(__name__)

DOCX_MIME_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

# Where generated drafts land in the document library, so they are one filter away from
# the uploads rather than mixed in with them.
DRAFTS_FOLDER = "Drafts"


def get_template_or_400(template_id: str) -> Template:
    template = get_template(template_id)
    if template is None:
        raise envelope.validation("That template does not exist.", {"template_id": template_id})
    return template


def compute_missing_fields(template: Template, fields: dict) -> list[str]:
    return [
        field.name
        for field in template.fields
        if field.required and not str(fields.get(field.name, "")).strip()
    ]


def _auto_fill_from_case(fields: dict, case: Case) -> dict:
    """Court and case number come from the firm's own case record when the caller left
    them blank. That is reading the tenant's database, not inventing anything."""
    filled = dict(fields)
    for key, value in (
        ("court_name", case.court_name),
        ("case_number", case.case_number or case.cnr),
    ):
        if not filled.get(key) and value:
            filled[key] = value
    return filled


async def _store_docx(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    case_id: uuid.UUID | None,
    template: Template,
    markdown: str,
) -> Document:
    document = Document(
        tenant_id=tenant_id,
        case_id=case_id,
        name=f"{template.name}.docx",
        folder=DRAFTS_FOLDER,
        mime_type=DOCX_MIME_TYPE,
        size_bytes=0,
        storage_key="",
        uploaded_by=user_id,
        # Nothing has to be extracted from a document we generated — the Markdown the
        # DOCX was rendered from *is* its text, so search sees the draft immediately
        # instead of queueing OCR against a file that was never scanned.
        ocr_status="done",
        ocr_text=markdown,
        confirmed=True,
    )
    session.add(document)
    await session.flush()

    docx_bytes = docx_generator.markdown_to_docx_bytes(markdown)
    document.storage_key = storage.storage_key(
        str(tenant_id), str(document.id), f"{template.id}.docx"
    )
    document.size_bytes = len(docx_bytes)
    await storage.put_object(document.storage_key, docx_bytes)
    await session.commit()

    return document


async def draft_document(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    template_id: str,
    case: Case | None,
    fields: dict,
    language: str = "en",
) -> dict:
    """The B.7 `draft` result shape: document_markdown, docx_url, missing_fields."""
    template = get_template_or_400(template_id)

    effective_fields = _auto_fill_from_case(fields, case) if case is not None else dict(fields)
    missing_fields = compute_missing_fields(template, effective_fields)

    system, user = build_draft_prompt(
        template_id=template.id,
        template_name=template.name,
        instructions=template.instructions,
        fields=effective_fields,
        language=language,
    )
    document_markdown = await complete(system=system, user=user)

    document = await _store_docx(
        session,
        tenant_id=tenant_id,
        user_id=user_id,
        case_id=case.id if case is not None else None,
        template=template,
        markdown=document_markdown,
    )

    return {
        "document_markdown": document_markdown,
        "docx_url": storage.build_download_url(str(document.id)),
        "document_id": str(document.id),
        "missing_fields": missing_fields,
    }
