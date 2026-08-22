"""Splitting extracted text into overlapping chunks (C.8).

The plan asks for "~800 tokens with overlap". This counts words instead, because a
tokenizer is a large dependency to add for one length heuristic and every provider
tokenises differently anyway — ~600 words is a fair stand-in for ~800 tokens of the
English/Hindi mix these documents contain. If that stops being good enough, swapping
in a real tokenizer is a change to this one function.

The overlap is the point: a sentence that straddles a boundary is still whole on one
side of it, so a search or a summary never loses the clause that spans the split.
"""

from app.core.config import get_settings

settings = get_settings()


def chunk_text(
    text: str,
    *,
    chunk_words: int | None = None,
    overlap_words: int | None = None,
) -> list[str]:
    chunk_words = chunk_words or settings.document_chunk_words
    overlap_words = overlap_words or settings.document_chunk_overlap_words

    words = text.split()
    if not words:
        return []

    if len(words) <= chunk_words:
        return [text.strip()]

    # An overlap at or above the chunk size would step by zero and never terminate.
    step = max(chunk_words - overlap_words, 1)
    chunks = []

    for start in range(0, len(words), step):
        chunk = " ".join(words[start : start + chunk_words])
        if chunk.strip():
            chunks.append(chunk.strip())
        # Without this the trailing windows are all suffixes of the last full chunk —
        # duplicated text, and a final chunk of two words.
        if start + chunk_words >= len(words):
            break

    return chunks
