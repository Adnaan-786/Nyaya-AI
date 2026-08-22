"""C.9 researcher step 1: turn a lawyer's question into a searchable English query.

Indian lawyers type in Hinglish ("Section 138 mein interim compensation kab milta
hai?"), and a keyword index of English judgments will not match that. Normalising
first also pulls out the sections, acts, years and courts the question mentions, which
are the filters retrieval actually wants.
"""

import logging

from app.ai.parsing import parse_json_object
from app.ai.prompts import build_query_normalize_prompt
from app.integrations.llm import complete

logger = logging.getLogger(__name__)


async def normalize_query(query: str) -> dict:
    """Returns `{"english_query", "sections", "acts", "years", "courts"}`.

    Falls back to passing the query through untouched when the model's reply is not
    usable, so a normalisation hiccup degrades retrieval rather than blocking it.
    """
    system, user = build_query_normalize_prompt(query)
    raw = await complete(system=system, user=user, max_tokens=512, json_mode=True)
    parsed = parse_json_object(raw, task="normalize_legal_query")

    if parsed.get("english_query"):
        return {
            "english_query": parsed["english_query"],
            "sections": parsed.get("sections") or [],
            "acts": parsed.get("acts") or [],
            "years": parsed.get("years") or [],
            "courts": parsed.get("courts") or [],
        }

    return {"english_query": query, "sections": [], "acts": [], "years": [], "courts": []}
