"""
Prompt builders for module M7's summarizer.

Every system prompt starts with a `TASK: <name>` line -- this is the
seam `app/ai/fake_llm.py` reads to fabricate a schema-correct fake
response in FAKE_MODE, and it also just makes the real prompts
self-documenting.
"""

_TYPE_FOCUS = {
    "chargesheet": (
        "Focus on: accused name(s), FIR number, police station, "
        "sections of law invoked, witness list, evidence list, and a "
        "chronological timeline of events."
    ),
    "judgment": (
        "Focus on: the parties, the issues framed, the court's holding, "
        "the ratio decidendi, and the relief granted."
    ),
    "notice": (
        "Focus on: the sender and recipient, the demand or grievance "
        "raised, the deadline given, and the consequence threatened if "
        "unmet."
    ),
    "agreement": (
        "Focus on: the parties, the subject matter, key obligations of "
        "each party, the term/duration, and any termination clause."
    ),
    "other": "Focus on the key facts, dates, and any legal provisions mentioned.",
}


def build_classification_prompt(text_excerpt: str) -> tuple[str, str]:
    system = (
        "TASK: classify_doc_type\n"
        "You are a legal document classifier for an Indian law-firm "
        "practice-management tool. Read the excerpt and respond with "
        "exactly one word: chargesheet, judgment, notice, agreement, "
        "or other. No punctuation, no explanation."
    )
    user = text_excerpt[:3000]
    return system, user


def build_extraction_prompt(doc_type: str, text: str, *, language: str = "en") -> tuple[str, str]:
    focus = _TYPE_FOCUS.get(doc_type, _TYPE_FOCUS["other"])
    lang_instruction = (
        "Write summary_markdown in Hindi." if language == "hi" else "Write summary_markdown in English."
    )

    system = (
        f"TASK: extract_summary_{doc_type}\n"
        "You are a legal document summarizer for an Indian law-firm "
        "practice-management tool. Extract information from the "
        "document text and respond with ONLY a JSON object (no "
        "markdown fences, no commentary) with exactly these keys: "
        '"summary_markdown" (string, a few sentences), "key_points" '
        '(array of strings), "parties" (array of strings), '
        '"sections_invoked" (array of strings, e.g. "Section 302 IPC"), '
        '"dates" (array of strings, as they appear in the text). '
        f"{focus} {lang_instruction} Never invent facts not present in "
        "the text."
    )
    return system, text


def build_reduce_prompt(partial_summaries: list[str], *, language: str = "en") -> tuple[str, str]:
    """Combines map-step partial summaries for a long, chunked document."""
    lang_instruction = "Respond in Hindi." if language == "hi" else "Respond in English."
    system = (
        "TASK: extract_summary_reduce\n"
        "You are combining several partial summaries of consecutive "
        "sections of the same legal document into one coherent "
        "summary. Respond with ONLY a JSON object with exactly these "
        'keys: "summary_markdown" (string), "key_points" (array of '
        'strings, deduplicated, at most 8). '
        f"{lang_instruction} Do not invent facts not present in the "
        "partial summaries."
    )
    user = "\n\n---\n\n".join(partial_summaries)
    return system, user
