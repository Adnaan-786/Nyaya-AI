import json
import re

from app.ai.prompts import build_query_normalize_prompt
from app.core.logging import get_logger
from app.integrations.llm import complete

logger = get_logger(__name__)

_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


async def normalize_query(query: str) -> dict:
    """
    Returns {"english_query", "sections", "acts", "years", "courts"}.
    Falls back to a pass-through if the model's response isn't
    parseable JSON, so a normalization hiccup never blocks retrieval
    entirely.
    """
    system, user = build_query_normalize_prompt(query)
    raw = await complete(system=system, user=user, max_tokens=512)

    cleaned = _JSON_FENCE_RE.sub("", raw).strip()
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict) and parsed.get("english_query"):
            return {
                "english_query": parsed["english_query"],
                "sections": parsed.get("sections") or [],
                "acts": parsed.get("acts") or [],
                "years": parsed.get("years") or [],
                "courts": parsed.get("courts") or [],
            }
    except json.JSONDecodeError:
        pass

    logger.warning("query_normalize_parse_failed", raw_preview=raw[:200])
    return {"english_query": query, "sections": [], "acts": [], "years": [], "courts": []}
