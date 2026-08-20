"""
Indian Kanoon provider abstraction, same shape as module M5's
ECourtsProvider: one interface, swappable implementations
(FixtureProvider for offline/default, a real HTTP provider behind an
API key). Plan C.9: "Indian Kanoon API search (keyword + filters) ...
citation verification: confirm the document ID exists via the API and
the source_url resolves."
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


class IndianKanoonProviderError(Exception):
    """Raised when the Indian Kanoon data source is unavailable or errors."""


@dataclass
class KanoonResult:
    doc_id: str
    case_title: str
    court: str
    year: int
    source_url: str
    snippet: str


class IndianKanoonProvider(ABC):
    @abstractmethod
    async def search(self, query: str, *, top_k: int) -> list[KanoonResult]:
        """Keyword search; returns up to top_k results ordered by relevance."""

    @abstractmethod
    async def fetch_document(self, doc_id: str) -> KanoonResult | None:
        """Fetches one document by ID, for citation verification. None if it doesn't exist."""
