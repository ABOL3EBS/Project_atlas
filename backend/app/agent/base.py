from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.embeddings.base import EmbeddingProvider
from app.memory.conversation_store import ConversationStore
from app.memory.selector import MemorySelector
from app.retrieval.base import VectorStore
from app.retrieval.retriever import RetrievedChunk, Retriever


@dataclass
class ToolContext:
    """Everything a tool needs to do its job for one user turn."""

    knowledge_base_id: str
    retriever: Retriever
    vector_store: VectorStore
    documents: list[dict] = field(default_factory=list)
    conversation_id: str | None = None
    embedding_provider: EmbeddingProvider | None = None
    memory_store: ConversationStore | None = None
    memory_selector: MemorySelector | None = None


@dataclass
class ToolResult:
    evidence: list[RetrievedChunk] = field(default_factory=list)
    summary: str | None = None


class Tool(ABC):
    name: str
    description: str
    input_schema: dict

    @abstractmethod
    async def execute(self, context: ToolContext, arguments: dict) -> ToolResult:
        raise NotImplementedError


def validate_tool_arguments(
    tool: Tool, arguments: dict, default_query: str
) -> list[str]:
    """Return a list of human-readable problems, or [] when valid.

    ``default_query`` is used to fill in a missing ``query``/``question``
    required field so a queryless direct search still has a search term.
    """
    problems: list[str] = []
    schema = tool.input_schema
    required = schema.get("required", [])
    properties = schema.get("properties", {})

    for key in required:
        if key not in arguments:
            if key in {"query", "question"}:
                arguments[key] = default_query
                continue
            problems.append(f"missing required argument '{key}'")
            continue
        expected = properties.get(key, {}).get("type")
        value = arguments[key]
        if not _matches_type(value, expected):
            problems.append(f"argument '{key}' must be {expected}")
    return problems


def _matches_type(value: Any, expected: str | None) -> bool:
    if expected is None:
        return True
    if expected == "string":
        return isinstance(value, str) and bool(value.strip())
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "array":
        return isinstance(value, list) and len(value) > 0
    if expected == "boolean":
        return isinstance(value, bool)
    return True