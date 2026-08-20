"""
Embeddings for doc_chunks.embedding (pgvector). Plan C.1: "Multilingual
embedding model (e.g. text-embedding-3-large or open multilingual
alternative) ... Must handle Hindi + English + legal English."

FAKE_MODE produces deterministic, hash-based vectors so the whole
chunk -> embed -> pgvector-search pipeline is exercisable end-to-end
offline, without needing an LLM provider API key -- same philosophy as
every other external integration in this codebase. The real call is
left as a clearly-marked stub: no OpenAI/other API key is configured
here yet, matching the "don't build against guessed credentials"
decision already made for the eCourts/OCR providers.
"""

import hashlib
import struct

from app.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


def _fake_embedding(text: str) -> list[float]:
    """
    Deterministic pseudo-embedding: repeats a SHA-256-seeded sequence
    to fill `embedding_dimensions`, normalized to roughly unit length.
    Same input text always yields the same vector, so cosine-similarity
    search behaves sensibly (near-duplicate chunks land close
    together) without calling any external API.
    """
    dims = settings.embedding_dimensions
    seed = hashlib.sha256(text.encode("utf-8")).digest()

    values: list[float] = []
    while len(values) < dims:
        seed = hashlib.sha256(seed).digest()
        # unpack 8 signed shorts per 16-byte digest chunk, scaled to [-1, 1]
        for i in range(0, len(seed) - 1, 2):
            if len(values) >= dims:
                break
            (raw,) = struct.unpack_from("<h", seed, i)
            values.append(raw / 32768.0)

    return values[:dims]


async def embed_texts(texts: list[str]) -> list[list[float]]:
    if settings.embedding_provider == "fake" or settings.fake_mode:
        return [_fake_embedding(t) for t in texts]

    raise NotImplementedError(
        "Real embedding provider (e.g. OpenAI text-embedding-3-large) is "
        "not configured yet. Set EMBEDDING_PROVIDER=fake (or FAKE_MODE=true) "
        "for now, or implement the HTTP call once OPENAI_API_KEY is "
        "provisioned."
    )
