import json
import re

from app.ai.prompts import build_risk_clause_prompt
from app.core.logging import get_logger
from app.integrations.llm import complete

logger = get_logger(__name__)

_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)

# Matches numbered clauses like "1.", "1.1", "(a)", "Clause 3:" at the
# start of a line -- common in Indian legal drafting.
_NUMBERED_CLAUSE_RE = re.compile(
    r"(?:^|\n)\s*(?:\d+(?:\.\d+)*\.?|\([a-zA-Z]\)|Clause\s+\d+:?)\s+",
)

MAX_CLAUSES = 40  # guardrail: cap per-clause LLM calls on a pathological document


def _parse_json_response(raw: str) -> dict:
    cleaned = _JSON_FENCE_RE.sub("", raw).strip()
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    logger.warning("risk_review_json_parse_failed", raw_preview=raw[:200])
    return {}


def segment_clauses(text: str) -> list[str]:
    """
    Splits contract text into clauses (plan C.9: "clause segmentation").
    Prefers numbered-clause boundaries (standard in Indian legal
    drafting); falls back to paragraph breaks, then to the whole
    document as one "clause" if neither pattern is present.
    """
    text = text.strip()
    if not text:
        return []

    numbered_splits = [c.strip() for c in _NUMBERED_CLAUSE_RE.split(text) if c.strip()]
    if len(numbered_splits) > 1:
        return numbered_splits[:MAX_CLAUSES]

    paragraph_splits = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if len(paragraph_splits) > 1:
        return paragraph_splits[:MAX_CLAUSES]

    return [text]


async def assess_clause(clause_text: str) -> dict:
    system, user = build_risk_clause_prompt(clause_text)
    raw = await complete(system=system, user=user, max_tokens=512)
    parsed = _parse_json_response(raw)

    severity = parsed.get("severity")
    if severity not in ("high", "medium", "low"):
        severity = "low"

    return {
        "severity": severity,
        "clause_text": clause_text,
        "explanation": parsed.get("explanation") or "",
        "suggestion": parsed.get("suggestion") or "",
    }


async def review_document(text: str) -> dict:
    """Returns the AIJob.result shape for type="risk_review" (contract B.7)."""
    clauses = segment_clauses(text)

    if not clauses:
        return {"risks": []}

    risks = [await assess_clause(clause) for clause in clauses]

    return {"risks": risks}
