"""Prompt builders for the C.9 AI tasks: summarize, draft, risk review, research.

Every system prompt opens with a literal `TASK: <name>` line. That is the seam
`app/ai/fake_llm.py` reads to fabricate a schema-correct fake response with no
provider configured, which is what lets the whole pipeline — including the JSON
parsing at each call site — run and be tested offline.

Each builder returns `(system, user)` rather than calling the model itself, so the
prompt is testable on its own and every completion goes through the one provider
switch in `app/integrations/llm.py`.
"""

import json

_TYPE_FOCUS = {
    "chargesheet": (
        "Focus on: accused name(s), FIR number, police station, sections of law "
        "invoked, witness list, evidence list, and a chronological timeline of events."
    ),
    "judgment": (
        "Focus on: the parties, the issues framed, the court's holding, the ratio "
        "decidendi, and the relief granted."
    ),
    "notice": (
        "Focus on: the sender and recipient, the demand or grievance raised, the "
        "deadline given, and the consequence threatened if unmet."
    ),
    "agreement": (
        "Focus on: the parties, the subject matter, key obligations of each party, "
        "the term/duration, and any termination clause."
    ),
    "other": "Focus on the key facts, dates, and any legal provisions mentioned.",
}


def build_classification_prompt(text_excerpt: str) -> tuple[str, str]:
    system = (
        "TASK: classify_doc_type\n"
        "You are a legal document classifier for an Indian law-firm practice-management "
        "tool. Read the excerpt and respond with exactly one word: chargesheet, "
        "judgment, notice, agreement, or other. No punctuation, no explanation."
    )
    return system, text_excerpt[:3000]


def build_extraction_prompt(
    doc_type: str, text: str, *, language: str = "en"
) -> tuple[str, str]:
    focus = _TYPE_FOCUS.get(doc_type, _TYPE_FOCUS["other"])
    lang_instruction = (
        "Write summary_markdown in Hindi."
        if language == "hi"
        else "Write summary_markdown in English."
    )

    system = (
        f"TASK: extract_summary_{doc_type}\n"
        "You are a legal document summarizer for an Indian law-firm "
        "practice-management tool. Extract information from the document text and "
        "respond with ONLY a JSON object (no markdown fences, no commentary) with "
        'exactly these keys: "summary_markdown" (string, a few sentences), '
        '"key_points" (array of strings), "parties" (array of strings), '
        '"sections_invoked" (array of strings, e.g. "Section 302 IPC"), "dates" '
        "(array of strings, as they appear in the text). "
        f"{focus} {lang_instruction} Never invent facts not present in the text."
    )
    return system, text


def build_reduce_prompt(
    partial_summaries: list[str], *, language: str = "en"
) -> tuple[str, str]:
    """Combines map-step partial summaries for a long, chunked document."""
    lang_instruction = "Respond in Hindi." if language == "hi" else "Respond in English."
    system = (
        "TASK: extract_summary_reduce\n"
        "You are combining several partial summaries of consecutive sections of the "
        "same legal document into one coherent summary. Respond with ONLY a JSON "
        'object with exactly these keys: "summary_markdown" (string), "key_points" '
        "(array of strings, deduplicated, at most 8). "
        f"{lang_instruction} Do not invent facts not present in the partial summaries."
    )
    return system, "\n\n---\n\n".join(partial_summaries)


def build_risk_clause_prompt(clause_text: str) -> tuple[str, str]:
    """C.9's per-clause risk prompt: severity, explanation, suggestion."""
    system = (
        "TASK: risk_review_clause\n"
        "You are a legal risk reviewer for an Indian law firm. Read the contract "
        "clause and assess it for risk to the client. Respond with ONLY a JSON object "
        'with exactly these keys: "severity" (one of "high", "medium", "low"), '
        '"explanation" (string, why this clause is risky or not), "suggestion" '
        "(string, a concrete redraft or negotiation point). If the clause presents no "
        'meaningful risk, use severity "low" and say so plainly.'
    )
    return system, clause_text


def build_draft_prompt(
    *,
    template_id: str,
    template_name: str,
    instructions: str,
    fields: dict,
    language: str = "en",
) -> tuple[str, str]:
    """C.9's draftsman: prose sections filled from the caller's fields and case data.

    The fields go in the *user* message as JSON rather than being interpolated into
    the system prompt, so a client who types instructions into a field cannot rewrite
    the drafting rules with them.
    """
    lang_instruction = (
        "Write the document in Hindi." if language == "hi" else "Write the document in English."
    )

    system = (
        f"TASK: draft_{template_id}\n"
        f"You are drafting a {template_name} for an Indian law firm. {instructions} "
        "Use ONLY the facts given in the fields below — never invent names, dates, "
        f"amounts, or facts not provided. {lang_instruction} Respond with ONLY the "
        "document text in markdown (use headings for sections), no commentary before "
        "or after."
    )
    return system, json.dumps(fields, ensure_ascii=False, indent=2)


def build_query_normalize_prompt(query: str) -> tuple[str, str]:
    """C.9 researcher step 1: detect Hinglish/Hindi, extract legal signals (sections,
    acts, years, courts), and produce an English search query."""
    system = (
        "TASK: normalize_legal_query\n"
        "You are normalizing a legal research query (possibly in Hindi or Hinglish) "
        "for search against an Indian case-law database. Respond with ONLY a JSON "
        'object with exactly these keys: "english_query" (string, the query '
        'translated/rewritten in clear English), "sections" (array of strings, e.g. '
        '"Section 138"), "acts" (array of strings, e.g. "Negotiable Instruments '
        'Act"), "years" (array of integers), "courts" (array of strings, e.g. '
        '"Bombay High Court" if a specific court was mentioned). Use empty arrays '
        "where nothing was mentioned."
    )
    return system, query


def build_research_generation_prompt(
    query: str, fragments: list[dict], *, language: str = "en"
) -> tuple[str, str]:
    """C.9 researcher step 3: answer only from the retrieved fragments.

    `fragments` carries `{"index", "case_title", "court", "year", "snippet"}`. The
    model picks which fragments actually support the answer and says why; it never
    supplies citation metadata itself — that always comes back from our own retrieval
    data in `app/ai/researcher.py`. This is what makes verification meaningful: there
    is no path by which a case name the model invented can reach a citation.
    """
    lang_instruction = (
        "Write answer_markdown in Hindi."
        if language == "hi"
        else "Write answer_markdown in English."
    )

    system = (
        "TASK: research_generate\n"
        "You are a legal research assistant for an Indian law firm. Answer the query "
        "using ONLY the information in the numbered fragments below — do not use any "
        "outside knowledge, and do not invent case names, courts, or holdings not "
        "present in the fragments. Reference fragments inline using [N] markers where "
        "N is the fragment's index. If the fragments do not contain enough information "
        "to answer confidently, say so plainly rather than guessing. Respond with ONLY "
        'a JSON object with exactly these keys: "answer_markdown" (string, with inline '
        '[N] markers), "citations" (array of objects, each with "fragment_index" '
        '(integer) and "relevance_note" (string, one sentence on why this fragment '
        "supports the answer) — include only fragments you actually relied on). "
        f"{lang_instruction} Citation case names/courts must stay in English "
        "regardless of answer language."
    )

    user = json.dumps({"query": query, "fragments": fragments}, ensure_ascii=False, indent=2)
    return system, user
