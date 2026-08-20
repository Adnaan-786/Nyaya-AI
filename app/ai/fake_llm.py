"""
Deterministic, heuristic-based fake completions for FAKE_MODE.

Every AI prompt built in this codebase starts its *system* message
with a literal `TASK: <name>` tag (see app/ai/prompts.py). This module
reads that tag and fabricates a plausible, schema-correct response
using simple text heuristics over the *user* message (which carries
the actual document/query text) -- no LLM call, no network.

This exercises the real downstream JSON-parsing code paths (unlike
just special-casing "return a canned string"), so the pipeline is
genuinely testable end-to-end offline, the same philosophy already
used for OCR/embeddings/eCourts fixtures elsewhere in this codebase.
"""

import json
import re

_TASK_RE = re.compile(r"^TASK:\s*(\S+)", re.MULTILINE)

_DOC_TYPE_KEYWORDS = {
    "chargesheet": ["chargesheet", "fir no", "police station", "accused", "chief judicial"],
    "judgment": ["judgment", "judgement", "held that", "appeal", "hereby ordered", "j.\n"],
    "notice": ["notice is hereby given", "legal notice", "you are hereby called upon"],
    "agreement": ["party of the first part", "party of the second part", "this agreement", "witnesseth"],
}

_SECTION_RE = re.compile(r"[Ss]ection[s]?\s+\d+[A-Za-z]*(?:\([0-9a-zA-Z]+\))?")
_DATE_RE = re.compile(
    r"\b\d{1,2}[/-](?:\d{1,2}|[A-Za-z]{3,9})[/-]\d{2,4}\b"
)
_PARTY_RE = re.compile(
    r"([A-Z][A-Za-z .]{2,40})\s+(?:[Vv]s?\.?|[Vv]ersus)\s+([A-Z][A-Za-z .]{2,40})"
)


def _extract_task(system: str) -> str:
    match = _TASK_RE.search(system)
    return match.group(1) if match else "unknown"


def _sentences(text: str, limit: int) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()][:limit]


def _classify_doc_type(text: str) -> str:
    lowered = text.lower()
    scores = {
        doc_type: sum(1 for kw in keywords if kw in lowered)
        for doc_type, keywords in _DOC_TYPE_KEYWORDS.items()
    }
    best_type, best_score = max(scores.items(), key=lambda kv: kv[1])
    return best_type if best_score > 0 else "other"


def _extract_summary(text: str) -> dict:
    doc_type = _classify_doc_type(text)
    sentences = _sentences(text, 6)

    sections = sorted(set(_SECTION_RE.findall(text)))
    dates = sorted(set(_DATE_RE.findall(text)))

    parties: list[str] = []
    party_match = _PARTY_RE.search(text)
    if party_match:
        parties = [party_match.group(1).strip(), party_match.group(2).strip()]

    return {
        "summary_markdown": " ".join(sentences[:3]) or "No extractable text was found.",
        "key_points": sentences[:5],
        "parties": parties,
        "sections_invoked": sections[:10],
        "dates": dates[:10],
        "doc_type_detected": doc_type,
    }


def fake_complete(*, system: str, user: str) -> str:
    task = _extract_task(system)

    if task == "classify_doc_type":
        return _classify_doc_type(user)

    if task.startswith("extract_summary"):
        return json.dumps(_extract_summary(user))

    # Generic fallback for any future task: echo a short, clearly-fake
    # paraphrase so callers still get *something* parseable as prose.
    sentences = _sentences(user, 2)
    preview = " ".join(sentences) or user[:200]
    return f"[FAKE LLM RESPONSE for task={task}] {preview}"
