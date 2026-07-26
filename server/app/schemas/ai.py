"""AI job schemas (B.7).

The `*Result` models below are both the structured-output schema we hand to Claude
**and** the shape the Android client decodes. Making them one thing means the model
cannot return a field the app does not expect, and the app cannot expect a field the
model was never asked for.
"""

import datetime as dt
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# B.7: the app polls every 3s for up to 5 min, so an estimate beyond that is a lie.
MAX_ESTIMATED_SECONDS = 300


class SummarizeRequest(BaseModel):
    document_id: uuid.UUID
    doc_type_hint: str | None = None


class ResearchRequest(BaseModel):
    query: str = Field(min_length=3, max_length=2000)
    language: Literal["en", "hi"] = "en"
    conversation_id: uuid.UUID | None = None


class JobAcceptedOut(BaseModel):
    """The 202 body. B.7 fixes these three fields exactly."""

    job_id: uuid.UUID
    status: str
    estimated_seconds: int


class AiJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: str
    status: str
    input_ref: str | None = None
    result: dict | None = None
    error: str | None = None
    estimated_seconds: int
    created_at: dt.datetime
    completed_at: dt.datetime | None = None


# --- Structured output schemas (also the job `result` shapes in B.7) -------------


class SummarizeResult(BaseModel):
    """B.7 `summarize` result.

    Field names and types are the contract. `sections_invoked` matters for Indian
    practice specifically — a lawyer scanning a chargesheet wants the sections at a
    glance, so it is a first-class field rather than something buried in prose.
    """

    summary_markdown: str = Field(description="2-5 paragraph summary in Markdown.")
    key_points: list[str] = Field(description="Bulleted findings, most important first.")
    parties: list[str] = Field(description="Named parties: petitioners, respondents, accused.")
    sections_invoked: list[str] = Field(
        description="Statutory sections cited, e.g. 'Section 138 NI Act', 'IPC 420'."
    )
    dates: list[str] = Field(description="Significant dates as they appear in the document.")
    doc_type_detected: str = Field(
        description="e.g. chargesheet, order, agreement, notice, affidavit, judgment."
    )


class Citation(BaseModel):
    """B.11: citations must be tappable and must link to `source_url`."""

    case_title: str
    court: str
    year: str
    source_url: str
    relevance_note: str = Field(description="One sentence on why this authority applies.")


class ResearchResult(BaseModel):
    """B.7 `research` result.

    `confidence: insufficient` is not a failure — B.7 requires `answer_markdown` to
    explain that no reliable authority was found, and the app renders a distinct
    state for it rather than an empty list. A confident-sounding answer with no real
    authority behind it is the worst outcome this feature can produce.
    """

    answer_markdown: str
    citations: list[Citation]
    confidence: Literal["high", "medium", "insufficient"]
