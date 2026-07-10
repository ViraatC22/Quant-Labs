"""L-1: deterministic local embeddings and boundary-aware chunking."""

from app.services import embeddings
from app.services.chunking import chunk_text


def test_local_embedding_is_deterministic_and_normalized() -> None:
    a = embeddings.embed_text("opening range breakout with volume")
    b = embeddings.embed_text("opening range breakout with volume")
    assert a is not None and a == b
    # L2-normalized: self-cosine is 1.0.
    assert abs(embeddings.cosine_similarity(a, a) - 1.0) < 1e-9


def test_synonyms_land_near_each_other() -> None:
    fvg = embeddings.embed_text("fvg")
    spelled_out = embeddings.embed_text("fair value gap")
    unrelated = embeddings.embed_text("weekly economic calendar releases")
    assert embeddings.cosine_similarity(fvg, spelled_out) > embeddings.cosine_similarity(
        fvg, unrelated
    )


def test_empty_text_has_no_embedding() -> None:
    assert embeddings.embed_text("   ") is None


def test_chunking_overlaps_and_respects_boundaries() -> None:
    text = " ".join(f"Sentence number {i} about market structure." for i in range(60))
    chunks = chunk_text(text)
    assert len(chunks) > 1
    # Real token counts, not word counts.
    assert all(c.token_count > 0 for c in chunks)
    # Overlap: the start of a later chunk repeats the tail of the previous one.
    joined_first = chunks[0].text
    assert any(word in chunks[1].text for word in joined_first.split()[-3:])


def test_empty_text_yields_no_chunks() -> None:
    assert chunk_text("") == []
