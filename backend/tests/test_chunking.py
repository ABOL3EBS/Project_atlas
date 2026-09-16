from app.ingestion.chunking import (
    ChunkingConfig,
    chunk_document,
    estimate_tokens,
)
from app.ingestion.parsers import ParsedPage


def _pages(*texts: str) -> list[ParsedPage]:
    return [ParsedPage(text=text, page=index) for index, text in enumerate(texts, start=1)]


def test_chunks_stay_within_size_and_carry_page_metadata():
    config = ChunkingConfig(chunk_size=30, chunk_overlap=5)
    pages = _pages(" ".join(["word"] * 80))
    chunks = chunk_document("doc-1", "a.txt", pages, config)

    assert len(chunks) >= 2
    assert all(estimate_tokens(c.text) <= 35 for c in chunks)
    assert all(c.page == 1 for c in chunks)
    assert all(c.document_id == "doc-1" for c in chunks)
    assert [c.chunk_id for c in chunks] == ["doc-1-0", "doc-1-1", "doc-1-2"]


def test_consecutive_chunks_share_overlap():
    config = ChunkingConfig(chunk_size=20, chunk_overlap=5)
    pages = _pages(" ".join(["word"] * 60))
    chunks = chunk_document("doc-1", "a.txt", pages, config)

    assert len(chunks) >= 2
    first_tail = set(chunks[0].text.split()[-5:])
    assert first_tail.issubset(set(chunks[1].text.split()))


def test_oversized_paragraph_is_split_and_keeps_metadata():
    config = ChunkingConfig(chunk_size=10, chunk_overlap=2)
    long_paragraph = " ".join(["word"] * 50)
    chunks = chunk_document("doc-1", "a.txt", _pages("intro.\n\n" + long_paragraph), config)

    assert len(chunks) >= 5
    assert all(c.page == 1 for c in chunks)


def test_pages_keep_their_own_page_number():
    config = ChunkingConfig(chunk_size=10, chunk_overlap=2)
    chunks = chunk_document(
        "doc-1",
        "a.txt",
        _pages(
            " ".join(["one"] * 30),
            " ".join(["two"] * 30),
            " ".join(["three"] * 30),
        ),
        config,
    )
    assert chunks[0].page == 1
    assert chunks[-1].page == 3
    assert {chunk.page for chunk in chunks} == {1, 2, 3}