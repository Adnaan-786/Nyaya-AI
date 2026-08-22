"""C.9 contract risk review: segment into clauses, then assess each one on its own.

Per-clause rather than whole-document because that is how the result is used — the app
shows a list a lawyer works down, and each row needs its own severity, its own
explanation, and a suggestion attached to the exact text it is about. A single
whole-document prompt returns prose no row can be built from.
"""

import logging
import re

from app.ai.parsing import parse_json_object
from app.ai.prompts import build_risk_clause_prompt
from app.integrations.llm import complete

logger = logging.getLogger(__name__)

# Numbered clauses like "1.", "1.1", "(a)", "Clause 3:" at the start of a line —
# standard in Indian legal drafting, and a far better boundary than a blank line
# because a single clause routinely runs to several paragraphs.
_NUMBERED_CLAUSE_RE = re.compile(
    r"(?:^|\n)\s*(?:\d+(?:\.\d+)*\.?|\([a-zA-Z]\)|Clause\s+\d+:?)\s+",
)

# One completion per clause, so an adversarial (or merely enormous) contract would
# otherwise fan out into hundreds of calls against a rate-limited provider.
MAX_CLAUSES = 40

_SEVERITIES = ("high", "medium", "low")


def segment_clauses(text: str) -> list[str]:
    """Numbered boundaries first, then paragraph breaks, then the whole document.

    The fallback chain matters: an OCRed contract often loses its numbering, and
    returning nothing for it would silently report a risk-free agreement.
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
    raw = await complete(system=system, user=user, max_tokens=512, json_mode=True)
    parsed = parse_json_object(raw, task="risk_review_clause")

    severity = parsed.get("severity")
    if severity not in _SEVERITIES:
        # "low" rather than "high" on a malformed reply: an unreadable severity is not
        # evidence of risk, and a wall of false high-severity rows is how a lawyer
        # learns to ignore the whole screen.
        severity = "low"

    return {
        "severity": severity,
        "clause_text": clause_text,
        "explanation": parsed.get("explanation") or "",
        "suggestion": parsed.get("suggestion") or "",
    }


async def review_document(text: str) -> dict:
    """The B.7 `risk_review` result shape: `{"risks": [...]}`."""
    clauses = segment_clauses(text)
    if not clauses:
        return {"risks": []}

    return {"risks": [await assess_clause(clause) for clause in clauses]}
