"""The real Indian Kanoon API provider, still a stub.

No subscription is provisioned, so writing the HTTP parsing now would be guessing at a
response shape — the same policy the eCourts commercial providers follow. Fill in
`search`/`fetch_document` against their documented endpoints once
`INDIANKANOON_API_KEY` exists.

It raises `IndianKanoonProviderError` rather than `NotImplementedError` deliberately.
Every caller already handles that exception by reporting no verified authority, so
someone setting the key before this is implemented gets honest "nothing found"
research instead of a background worker dying on an unhandled error.
"""

from app.integrations.indian_kanoon.base import (
    IndianKanoonProvider,
    IndianKanoonProviderError,
    KanoonResult,
)

UNIMPLEMENTED = (
    "The Indian Kanoon API is not implemented yet. Unset INDIANKANOON_API_KEY to use "
    "the offline fixture corpus."
)


class RealIndianKanoonProvider(IndianKanoonProvider):
    async def search(self, query: str, *, top_k: int) -> list[KanoonResult]:
        raise IndianKanoonProviderError(UNIMPLEMENTED)

    async def fetch_document(self, doc_id: str) -> KanoonResult | None:
        raise IndianKanoonProviderError(UNIMPLEMENTED)
