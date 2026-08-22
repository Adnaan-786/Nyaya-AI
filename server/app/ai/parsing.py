"""Lenient JSON parsing for the structured AI tasks.

Every prompt in `app/ai/prompts.py` forbids a code fence, but only Groq's JSON mode
makes that a guarantee, so a ```json wrapper stays a live possibility on any other
provider and is not worth failing a job over.

Unparseable output returns `{}` rather than raising: each caller here already has a
safe shape to fall back to (an empty summary, a pass-through query, a "low" severity),
and every one of them is better for the lawyer than a failed job. The research path is
the deliberate exception — `app/ai/researcher.py` turns an empty parse into
`insufficient` confidence with no citations, because there a missing answer is the
*only* acceptable failure.
"""

import json
import logging
import re

logger = logging.getLogger(__name__)

_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def parse_json_object(raw: str, *, task: str) -> dict:
    cleaned = _JSON_FENCE_RE.sub("", raw).strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        parsed = None

    if isinstance(parsed, dict):
        return parsed

    # The preview is what makes this diagnosable: "the model returned prose" and "the
    # model returned a JSON *array*" look identical from the empty dict alone.
    logger.warning("%s: response was not a JSON object (starts: %r)", task, raw[:200])
    return {}
