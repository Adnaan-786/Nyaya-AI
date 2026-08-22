"""Indian Kanoon provider abstraction: one interface, swappable implementations.

Same shape as the eCourts integration — a fixture provider that works offline and is
the default, and a real HTTP provider behind an API key (C.1's "Indian Kanoon API
subscription"). The researcher only ever talks to this interface, so the corpus behind
a citation can be swapped without touching the verification logic that decides whether
a citation is allowed to reach a lawyer.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


class IndianKanoonProviderError(Exception):
    """The case-law source is unavailable or errored.

    Callers degrade to "no authority found" on this rather than failing the job: an
    unreachable index is a reason to say nothing was verified, never a reason to fall
    back on the model's own recall of case names.
    """


@dataclass(frozen=True)
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
        """Keyword search; returns up to `top_k` results ordered by relevance."""

    @abstractmethod
    async def fetch_document(self, doc_id: str) -> KanoonResult | None:
        """One document by ID, for citation verification. None if it does not exist."""
