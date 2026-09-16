from app.retrieval.retriever import RetrievedChunk
from app.services.chat_service import NOT_FOUND_MESSAGE, ChatService
from tests.conftest import FakeVectorStore


class StubRetriever:
    def __init__(self, chunks: list[RetrievedChunk]):
        self._chunks = chunks

    def search(
        self, knowledge_base_id: str, query: str, top_k: int | None = None
    ) -> list[RetrievedChunk]:
        return self._chunks


class RecordingLLM:
    def __init__(self):
        self.system_calls: list[str] = []

    async def generate(
        self, prompt: str, *, system: str | None = None, json_mode: bool = False
    ) -> str:
        return "not a decision"

    async def stream(self, prompt: str, *, system: str | None = None):
        self.system_calls.append(system or "")
        yield "token"


def _chunk(score: float) -> RetrievedChunk:
    return RetrievedChunk(
        text="evidence",
        chunk_id="chunk-1",
        document_id="doc-1",
        document_name="a.md",
        page=None,
        section=None,
        score=score,
    )


async def _events(service: ChatService) -> list[dict]:
    return [event async for event in service.run("kb-a", "question")]


def _service(chunks: list[RetrievedChunk], llm: RecordingLLM | None = None) -> ChatService:
    return ChatService(
        retriever=StubRetriever(chunks),
        llm_provider=llm or RecordingLLM(),
        grounding_threshold=0.45,
        vector_store=FakeVectorStore(),
    )


async def test_zero_results_reported_not_found():
    events = await _events(_service([]))
    assert any(event["type"] == "answer" and event["text"] == NOT_FOUND_MESSAGE for event in events)
    assert all(event["type"] != "token" for event in events)


async def test_below_threshold_reported_not_found():
    events = await _events(_service([_chunk(0.30)]))
    assert any(event["type"] == "answer" and event["text"] == NOT_FOUND_MESSAGE for event in events)
    assert all(event["type"] != "token" for event in events)
    retrieval = next(event for event in events if event["type"] == "retrieval")
    assert retrieval["count"] == 1


async def test_threshold_boundary_is_grounded():
    llm = RecordingLLM()
    events = await _events(_service([_chunk(0.45)], llm))
    assert any(event["type"] == "token" for event in events)
    assert llm.system_calls


async def test_above_threshold_generates_answer_with_citations():
    llm = RecordingLLM()
    events = await _events(_service([_chunk(0.85)], llm))
    tokens = "".join(event["text"] for event in events if event["type"] == "token")
    assert tokens == "token"
    done = next(event for event in events if event["type"] == "done")
    assert done["citations"][0]["chunk_id"] == "chunk-1"


async def test_mixed_relevant_and_irrelevant_grounds_on_best_evidence():
    llm = RecordingLLM()
    chunks = [_chunk(0.25), _chunk(0.70)]
    events = await _events(_service(chunks, llm))
    assert any(event["type"] == "token" for event in events)