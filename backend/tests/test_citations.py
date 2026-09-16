from app.retrieval.retriever import RetrievedChunk
from app.services.chat_service import Citation, build_citations, verify_citations


def _chunk(
    chunk_id: str = "doc-1-0",
    document_id: str = "doc-1",
    document_name: str = "installation.pdf",
    page: int | None = 18,
    section: str | None = "Deployment",
    score: float = 0.9,
) -> RetrievedChunk:
    return RetrievedChunk(
        text="evidence text",
        chunk_id=chunk_id,
        document_id=document_id,
        document_name=document_name,
        page=page,
        section=section,
        score=score,
    )


def test_citations_built_from_retrieved_evidence():
    citations = build_citations([_chunk()])
    assert len(citations) == 1
    assert citations[0].chunk_id == "doc-1-0"
    assert citations[0].document_id == "doc-1"
    assert citations[0].document_name == "installation.pdf"
    assert citations[0].page == 18
    assert citations[0].section == "Deployment"


def test_citation_to_dict_omits_missing_metadata():
    citation = Citation(chunk_id="c", document_id="d", document_name="pricing.txt")
    exported = citation.to_dict()
    assert exported == {"chunk_id": "c", "document_id": "d", "document_name": "pricing.txt"}
    assert "page" not in exported
    assert "section" not in exported


def test_citation_includes_metadata_it_has():
    citation = Citation(
        chunk_id="c", document_id="d", document_name="pricing.txt", section="Pro Plan"
    )
    exported = citation.to_dict()
    assert exported["section"] == "Pro Plan"
    assert "page" not in exported


def test_verify_citations_keeps_only_retrieved_chunks():
    chunks = [_chunk()]

    fabricated = [
        Citation(chunk_id="fake-999", document_id="nope", document_name="ghost.pdf"),
    ]
    assert verify_citations(fabricated, chunks) == []


def test_verify_citations_accepts_matching_citation():
    chunks = [_chunk()]
    citation = Citation(
        chunk_id="doc-1-0",
        document_id="doc-1",
        document_name="installation.pdf",
        page=18,
        section="Deployment",
    )
    assert verify_citations([citation], chunks) == [citation]


def test_verify_citations_rejects_invented_page():
    chunks = [_chunk(page=None)]
    forged = Citation(
        chunk_id="doc-1-0",
        document_id="doc-1",
        document_name="installation.pdf",
        page=42,
    )
    assert verify_citations([forged], chunks) == []


def test_verify_citations_rejects_mismatched_metadata():
    chunks = [_chunk(page=5)]
    wrong = Citation(
        chunk_id="doc-1-0",
        document_id="doc-1",
        document_name="installation.pdf",
        page=7,
    )
    assert verify_citations([wrong], chunks) == []