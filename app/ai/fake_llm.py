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


_HIGH_RISK_TERMS = [
    "indemnify", "indemnification", "liquidated damages", "unlimited liability",
    "sole discretion", "non-refundable", "waive", "waiver of", "penalty",
    "forfeit", "irrevocable", "personal guarantee",
]
_MEDIUM_RISK_TERMS = [
    "terminate", "termination", "breach", "confidential", "warranty",
    "exclusive", "non-compete", "arbitration", "governing law",
]


def _assess_clause_risk(clause_text: str) -> dict:
    lowered = clause_text.lower()

    if any(term in lowered for term in _HIGH_RISK_TERMS):
        severity = "high"
        matched = next(term for term in _HIGH_RISK_TERMS if term in lowered)
        explanation = (
            f"This clause contains the term '{matched}', which typically "
            "shifts significant risk or obligation onto one party."
        )
        suggestion = (
            f"Negotiate to cap or remove the '{matched}' obligation, or "
            "add a mutual/reciprocal version of this clause."
        )
    elif any(term in lowered for term in _MEDIUM_RISK_TERMS):
        severity = "medium"
        matched = next(term for term in _MEDIUM_RISK_TERMS if term in lowered)
        explanation = (
            f"This clause involves '{matched}', which is worth reviewing "
            "for fairness and clarity of terms."
        )
        suggestion = f"Clarify the scope and conditions around '{matched}' before signing."
    else:
        severity = "low"
        explanation = "No significant risk indicators were found in this clause."
        suggestion = "No changes suggested."

    return {
        "severity": severity,
        "clause_text": clause_text,
        "explanation": explanation,
        "suggestion": suggestion,
    }


_ACT_RE = re.compile(r"[A-Z][a-zA-Z,\s]{2,60}\bAct\b(?:,?\s*\d{4})?")
_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")
_COURT_KEYWORDS = [
    "supreme court", "high court", "district court", "sessions court",
    "tribunal", "magistrate", "consumer commission", "family court",
]


def _normalize_legal_query(query: str) -> dict:
    sections = sorted(set(_SECTION_RE.findall(query)))
    acts = sorted({m.strip() for m in _ACT_RE.findall(query)})
    years = sorted({int(y) for y in re.findall(r"\b(?:19|20)\d{2}\b", query)})

    lowered = query.lower()
    courts = sorted({kw.title() for kw in _COURT_KEYWORDS if kw in lowered})

    return {
        "english_query": query,  # FAKE_MODE can't translate; real mode can.
        "sections": sections,
        "acts": acts,
        "years": years,
        "courts": courts,
    }


def _research_generate(payload_json: str) -> dict:
    try:
        payload = json.loads(payload_json)
    except json.JSONDecodeError:
        payload = {}

    fragments = payload.get("fragments", [])
    query = payload.get("query", "")

    if not fragments:
        return {
            "answer_markdown": (
                "No relevant authority was found in the available sources "
                f"for: {query}"
            ),
            "citations": [],
        }

    answer_parts = []
    citations = []
    for frag in fragments:
        idx = frag.get("index")
        answer_parts.append(
            f"{frag.get('case_title', 'Unknown case')} [{idx}] addressed a "
            f"related point: {frag.get('snippet', '')[:160]}"
        )
        citations.append(
            {
                "fragment_index": idx,
                "relevance_note": "Snippet keyword-matches the query in FAKE_MODE retrieval.",
            }
        )

    return {
        "answer_markdown": " ".join(answer_parts),
        "citations": citations,
    }


def _fake_draft_markdown(template_id: str, fields_json: str) -> str:
    """
    Deterministic fake draft: renders the given fields as a labeled
    markdown document. Not real prose, but genuinely built from the
    fields (never invented facts), and exercises the same
    markdown -> DOCX conversion path a real completion would.
    """
    try:
        fields = json.loads(fields_json)
    except json.JSONDecodeError:
        fields = {}

    title = template_id.replace("_", " ").title()
    lines = [f"# {title}", ""]

    for key, value in fields.items():
        label = key.replace("_", " ").title()
        lines.append(f"**{label}:** {value}")

    lines.append("")
    lines.append(
        "*This is a FAKE_MODE draft assembled directly from the fields "
        "above. Set LLM_PROVIDER=anthropic for real prose generation.*"
    )
    return "\n".join(lines)


def fake_complete(*, system: str, user: str) -> str:
    task = _extract_task(system)

    if task == "classify_doc_type":
        return _classify_doc_type(user)

    if task.startswith("extract_summary"):
        return json.dumps(_extract_summary(user))

    if task == "risk_review_clause":
        return json.dumps(_assess_clause_risk(user))

    if task == "normalize_legal_query":
        return json.dumps(_normalize_legal_query(user))

    if task == "research_generate":
        return json.dumps(_research_generate(user))

    if task.startswith("draft_"):
        template_id = task[len("draft_"):]
        return _fake_draft_markdown(template_id, user)

    # Generic fallback for any future task: echo a short, clearly-fake
    # paraphrase so callers still get *something* parseable as prose.
    sentences = _sentences(user, 2)
    preview = " ".join(sentences) or user[:200]
    return f"[FAKE LLM RESPONSE for task={task}] {preview}"
