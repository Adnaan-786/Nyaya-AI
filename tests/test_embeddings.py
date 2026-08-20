import asyncio

from app.config import get_settings
from app.integrations.embeddings import embed_texts

settings = get_settings()


def test_fake_embeddings_are_deterministic():
    vectors_a = asyncio.run(embed_texts(["hello world"]))
    vectors_b = asyncio.run(embed_texts(["hello world"]))

    assert vectors_a == vectors_b


def test_fake_embeddings_have_configured_dimensions():
    [vector] = asyncio.run(embed_texts(["some legal text about a contract"]))

    assert len(vector) == settings.embedding_dimensions
    assert all(-1.0 <= v <= 1.0 for v in vector)


def test_fake_embeddings_differ_for_different_text():
    [vector_a] = asyncio.run(embed_texts(["chargesheet under section 302"]))
    [vector_b] = asyncio.run(embed_texts(["rent agreement for commercial property"]))

    assert vector_a != vector_b


def test_fake_embeddings_batch_matches_individual_order():
    texts = ["first chunk of text", "second chunk of text", "third chunk of text"]
    batch = asyncio.run(embed_texts(texts))

    assert len(batch) == len(texts)
    for text, vector in zip(texts, batch):
        [individual] = asyncio.run(embed_texts([text]))
        assert vector == individual
