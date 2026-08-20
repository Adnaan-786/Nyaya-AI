from app.services.chunking import chunk_text


def test_chunk_text_short_input_returns_single_chunk():
    text = "This is a short document with only a few words."
    chunks = chunk_text(text, chunk_words=600, overlap_words=80)

    assert len(chunks) == 1
    assert chunks[0] == text


def test_chunk_text_empty_input_returns_no_chunks():
    assert chunk_text("", chunk_words=600, overlap_words=80) == []
    assert chunk_text("   ", chunk_words=600, overlap_words=80) == []


def test_chunk_text_splits_long_input_with_overlap():
    words = [f"word{i}" for i in range(1000)]
    text = " ".join(words)

    chunks = chunk_text(text, chunk_words=300, overlap_words=50)

    assert len(chunks) > 1

    # every chunk (except possibly the last) should be `chunk_words` long
    for chunk in chunks[:-1]:
        assert len(chunk.split()) == 300

    # overlap: the tail of one chunk should reappear at the head of the next
    first_chunk_words = chunks[0].split()
    second_chunk_words = chunks[1].split()
    assert first_chunk_words[-50:] == second_chunk_words[:50]


def test_chunk_text_covers_every_word_exactly_once_at_minimum():
    words = [f"w{i}" for i in range(50)]
    text = " ".join(words)

    chunks = chunk_text(text, chunk_words=10, overlap_words=2)
    all_chunk_words = set(" ".join(chunks).split())

    assert set(words) == all_chunk_words
