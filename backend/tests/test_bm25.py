from app.retrieval.bm25 import BM25Index, tokenize
from app.retrieval.retriever import RetrievedChunk

CORPUS = [
    "solar panels convert sunlight into electricity with monocrystalline "
    "efficiency near twenty percent",
    "nginx servers handle worker connections and proxy static files to clients",
    "documents that mention solar panels get a higher lexical overlap "
    "score for the query",
]


def _chunk(text: str, name: str = "doc.md") -> RetrievedChunk:
    return RetrievedChunk(
        text=text,
        chunk_id=f"{name}-0",
        document_id=name,
        document_name=name,
        page=None,
        section=None,
        score=1.0,
    )


def test_tokenize_lowercases_and_splits():
    assert tokenize("Solar-Panel, EFFICIENCY!") == ["solar", "panel", "efficiency"]


def test_score_prefers_term_overlap():
    index = BM25Index(CORPUS)
    assert index.score("solar efficiency monocrystalline", CORPUS[0]) > index.score(
        "solar efficiency monocrystalline", CORPUS[1]
    )


def test_idf_weights_rare_terms_higher():
    index = BM25Index(CORPUS)
    assert index._idf("nginx") > index._idf("solar")


def test_empty_query_scores_zero():
    index = BM25Index(CORPUS)
    assert index.score("", CORPUS[0]) == 0.0
    assert index.rerank("", [_chunk(CORPUS[0])]) == [_chunk(CORPUS[0])]


def test_rerank_orders_by_lexical_relevance_and_trims_top_k():
    index = BM25Index(CORPUS)
    candidates = [_chunk(CORPUS[1]), _chunk(CORPUS[2]), _chunk(CORPUS[0])]
    ranked = index.rerank("solar monocrystalline panels", candidates, top_k=2)
    assert [chunk.document_name for chunk in ranked] == ["doc.md", "doc.md"]
    assert ranked[0].text == CORPUS[0]


def test_full_rerank_returns_all_when_top_k_omitted():
    index = BM25Index(CORPUS)
    ranked = index.rerank("nginx", [_chunk(CORPUS[1]), _chunk(CORPUS[0])])
    assert len(ranked) == 2
    assert ranked[0].text == CORPUS[1]