"""C.8 chunking: the guarantees a retriever depends on."""

from app.services.chunking import chunk_text


def test_short_input_returns_a_single_chunk() -> None:
    text = "This is a short document with only a few words."
    assert chunk_text(text, chunk_words=600, overlap_words=80) == [text]


def test_empty_input_returns_no_chunks() -> None:
    assert chunk_text("", chunk_words=600, overlap_words=80) == []
    assert chunk_text("   ", chunk_words=600, overlap_words=80) == []


def test_long_input_splits_with_the_tail_repeated_at_the_next_head() -> None:
    """The overlap is the feature: a clause spanning a boundary survives on one side."""
    text = " ".join(f"word{i}" for i in range(1000))

    chunks = chunk_text(text, chunk_words=300, overlap_words=50)

    assert len(chunks) > 1
    for chunk in chunks[:-1]:
        assert len(chunk.split()) == 300
    assert chunks[0].split()[-50:] == chunks[1].split()[:50]


def test_every_word_survives_chunking() -> None:
    words = [f"w{i}" for i in range(50)]

    chunks = chunk_text(" ".join(words), chunk_words=10, overlap_words=2)

    assert set(" ".join(chunks).split()) == set(words)


def test_the_last_chunk_is_not_a_duplicate_of_the_one_before_it() -> None:
    """Without the early break, every trailing window is a suffix of the last full
    chunk — the same text re-embedded three more times."""
    text = " ".join(f"w{i}" for i in range(25))

    chunks = chunk_text(text, chunk_words=10, overlap_words=2)

    assert len(chunks) == len(set(chunks))
    assert not any(chunks[-1] in earlier for earlier in chunks[:-1])


def test_overlap_at_or_above_chunk_size_still_terminates() -> None:
    """A misconfigured overlap would step by zero and loop forever."""
    text = " ".join(f"w{i}" for i in range(40))

    chunks = chunk_text(text, chunk_words=10, overlap_words=10)

    assert chunks
    assert set(" ".join(chunks).split()) == {f"w{i}" for i in range(40)}


def test_defaults_come_from_settings() -> None:
    text = " ".join(f"w{i}" for i in range(2000))

    chunks = chunk_text(text)

    from app.core.config import get_settings

    assert len(chunks[0].split()) == get_settings().document_chunk_words
