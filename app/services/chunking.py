from app.config import get_settings

settings = get_settings()


def chunk_text(
    text: str,
    *,
    chunk_words: int | None = None,
    overlap_words: int | None = None,
) -> list[str]:
    """
    Splits `text` into overlapping word-count chunks.

    The plan specifies "~800 tokens with overlap" (C.8.2); we chunk by
    words rather than model-specific tokens to avoid pulling in a
    tokenizer dependency purely for this. ~600 words is a reasonable
    stand-in for ~800 tokens of legal English/Hindi mixed text; tune
    via DOCUMENT_CHUNK_WORDS if a real tokenizer-based count is added
    later (a drop-in swap in this one function).
    """
    chunk_words = chunk_words or settings.document_chunk_words
    overlap_words = overlap_words or settings.document_chunk_overlap_words

    words = text.split()
    if not words:
        return []

    if len(words) <= chunk_words:
        return [text.strip()]

    step = max(chunk_words - overlap_words, 1)
    chunks = []

    for start in range(0, len(words), step):
        chunk = " ".join(words[start : start + chunk_words])
        if chunk.strip():
            chunks.append(chunk.strip())
        if start + chunk_words >= len(words):
            break

    return chunks
