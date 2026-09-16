from app.memory.conversation_store import ConversationStore
from app.memory.selector import MemorySelector
from tests.conftest import FakeEmbeddingProvider


def test_ensure_conversation_creates_and_reuses(tmp_path):
    store = ConversationStore(str(tmp_path / "conversations.db"))
    conversation_id = store.ensure_conversation("kb-a")
    assert conversation_id
    assert store.ensure_conversation("kb-a", conversation_id) == conversation_id


def test_foreign_conversation_id_allocates_fresh(tmp_path):
    store = ConversationStore(str(tmp_path / "conversations.db"))
    first = store.ensure_conversation("kb-a")
    second = store.ensure_conversation("kb-b", first)
    assert second != first


def test_messages_persist_in_chronological_order(tmp_path):
    store = ConversationStore(str(tmp_path / "conversations.db"))
    conversation_id = store.ensure_conversation("kb-a")
    store.append_message(conversation_id, "user", "first")
    store.append_message(conversation_id, "assistant", "second")
    store.append_message(conversation_id, "user", "third")

    messages = store.list_messages(conversation_id)
    assert [message["content"] for message in messages] == ["first", "second", "third"]
    assert [message["role"] for message in messages] == ["user", "assistant", "user"]


def test_conversations_are_isolated_by_knowledge_base(tmp_path):
    store = ConversationStore(str(tmp_path / "conversations.db"))
    store.ensure_conversation("kb-a")
    store.ensure_conversation("kb-b")

    assert len(store.list_conversations("kb-a")) == 1
    assert len(store.list_conversations("kb-b")) == 1
    assert len(store.list_conversations("kb-c")) == 0


def test_get_conversation_is_knowledge_base_scoped(tmp_path):
    store = ConversationStore(str(tmp_path / "conversations.db"))
    conversation_id = store.ensure_conversation("kb-a")
    assert store.get_conversation("kb-a", conversation_id) is not None
    assert store.get_conversation("kb-b", conversation_id) is None


class DeterministicEmbedding(FakeEmbeddingProvider):
    def __init__(self, vectors: dict[str, list[float]]):
        self._vectors = vectors
        self._default = [0.0, 0.0, 0.0]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vectors.get(text, self._default) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vectors.get(text, self._default)


def _messages():
    return [
        {"role": "assistant", "content": "the quarterly budget is 40k"},
        {"role": "user", "content": "what about headcount?"},
        {"role": "assistant", "content": "headcount stays at 12"},
    ]


def test_selector_returns_most_relevant_and_never_exceeds_limit():
    vectors = {
        "budget": [1.0, 0.0, 0.0],
        "the quarterly budget is 40k": [1.0, 0.0, 0.0],
        "headcount": [0.0, 1.0, 0.0],
        "what about headcount?": [0.0, 1.0, 0.0],
        "headcount stays at 12": [0.0, 1.0, 0.0],
    }
    selector = MemorySelector(DeterministicEmbedding(vectors), max_results=3)
    selected = selector.select(_messages(), "budget")
    assert "the quarterly budget is 40k" in [m["content"] for m in selected]
    assert len(selected) <= 3


def test_selector_empty_input_returns_empty():
    selector = MemorySelector(FakeEmbeddingProvider())
    assert selector.select([], "anything") == []


def test_selector_keeps_recency_anchor_when_irrelevant():
    vectors = {
        "budget": [1.0, 0.0, 0.0],
        "the quarterly budget is 40k": [1.0, 0.0, 0.0],
        "what about headcount?": [1.0, 0.0, 0.0],
        "headcount stays at 12": [1.0, 0.0, 0.0],
    }
    selector = MemorySelector(DeterministicEmbedding(vectors), max_results=1)
    selected = selector.select(_messages(), "budget")
    assert selected[-1]["content"] == "headcount stays at 12"