"""
Real Indian Kanoon API provider. Left as a clearly-marked stub, same
policy as NAPIX/CommercialProvider (M5) and Document AI (M6): no API
subscription is configured here, so implementing HTTP parsing now
would just be guessing at a response shape. Once
INDIAN_KANOON_API_KEY is provisioned (plan C.1: "Indian Kanoon API
subscription"), fill in search()/fetch_document() below using their
documented endpoints.
"""

from app.config import get_settings
from app.integrations.indian_kanoon.base import IndianKanoonProvider, KanoonResult

settings = get_settings()


class RealIndianKanoonProvider(IndianKanoonProvider):
    async def search(self, query: str, *, top_k: int) -> list[KanoonResult]:
        raise NotImplementedError(
            "Real Indian Kanoon search is not configured. Set "
            "INDIAN_KANOON_API_KEY and INDIAN_KANOON_PROVIDER=indiankanoon, "
            "or leave INDIAN_KANOON_PROVIDER=fixture (default) for now."
        )

    async def fetch_document(self, doc_id: str) -> KanoonResult | None:
        raise NotImplementedError(
            "Real Indian Kanoon document fetch is not configured. Set "
            "INDIAN_KANOON_API_KEY and INDIAN_KANOON_PROVIDER=indiankanoon, "
            "or leave INDIAN_KANOON_PROVIDER=fixture (default) for now."
        )
