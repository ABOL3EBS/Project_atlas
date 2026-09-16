import json
from dataclasses import dataclass, field

from .base import validate_tool_arguments
from .registry import ToolRegistry

TOOL_SEARCH = "search_knowledge_base"
TOOL_RETRIEVE = "retrieve_document"
TOOL_COMPARE = "compare_documents"
TOOL_MEMORY = "get_conversation_context"
DIRECT = "none"

DEFAULT_SEARCH_TOP_K = 4


@dataclass
class PlannedAction:
    tool: str | None
    arguments: dict = field(default_factory=dict)

    @property
    def uses_tool(self) -> bool:
        return self.tool is not None


def build_planner_system(document_names: list[str], registry: ToolRegistry) -> str:
    documents = "\n".join(f"- {name}" for name in document_names) or "- (none yet)"
    search_args = (
        '{"query": "<self-contained search query>", "top_k": '
        + str(DEFAULT_SEARCH_TOP_K)
        + "}"
    )
    retrieve_args = '{"document": "<exact document name>"}'
    compare_args = '{"documents": ["<name1>", "<name2>"], "question": "<what to compare>"}'
    memory_args = '{"question": "<what to look for in memory>"}'
    example = (
        '{"tool": "search_knowledge_base", '
        '"arguments": {"query": "on-premise deployment minimum requirements", "top_k": '
        + str(DEFAULT_SEARCH_TOP_K) + "}}"
    )
    return (
        "You are the decision engine for Atlas, a document research agent.\n\n"
        f"Available documents in the current knowledge base:\n{documents}\n\n"
        "Decide whether the user's question needs the knowledge base, and if so, "
        "which single tool to use. Output ONLY a JSON object — no prose, no markdown fences.\n\n"
        "Tool choices:\n"
        f'- "{DIRECT}": answer directly without the knowledge base. Use ONLY for greetings, '
        "small talk, or questions about what Atlas can do. Never use it for questions about "
        "the uploaded documents.\n"
        f'- "{TOOL_SEARCH}": arguments {search_args}. Best default for any '
        "factual question about the "
        "documents. Write a clear search query, not a verbatim echo of the question.\n"
        f'- "{TOOL_RETRIEVE}": arguments {retrieve_args}. Use when the '
        "user asks about one whole document or you need its full content.\n"
        f'- "{TOOL_COMPARE}": arguments {compare_args}. '
        "Use when the user compares information across two or more documents.\n"
        f'- "{TOOL_MEMORY}": arguments {memory_args}. Use when '
        "the user refers to an earlier part of this conversation (\"what did we say about X\", "
        "\"that document\", \"the one we discussed\").\n\n"
        "Exact output shape. No keys outside the allowed tools, no extra fields. Example:\n"
        + example
    )


class DecisionParser:
    """Parses and validates the planner's JSON decision with a safe fallback.

    If the LLM returns malformed JSON, an unknown tool, or invalid arguments,
    the parser falls back to a knowledge-base search with the original question.
    This keeps the agent working in degraded mode instead of crashing, while
    genuine decisions (including 'none') still pass through.
    """

    def __init__(self, registry: ToolRegistry):
        self._registry = registry

    def parse(self, raw: str, *, default_query: str) -> PlannedAction:
        payload = _extract_json(raw)
        if not payload:
            return self._fallback(default_query)

        tool = payload.get("tool")
        if tool in {None, "", DIRECT}:
            return PlannedAction(tool=None)

        if not isinstance(tool, str) or not self._registry.has(tool):
            return self._fallback(default_query)

        arguments = payload.get("arguments")
        if not isinstance(arguments, dict):
            return self._fallback(default_query)

        cleaned = dict(arguments)
        problems = validate_tool_arguments(
            self._registry.get(tool), cleaned, default_query
        )
        if problems:
            return self._fallback(default_query)

        return PlannedAction(tool=tool, arguments=cleaned)

    def _fallback(self, default_query: str) -> PlannedAction:
        return PlannedAction(
            tool=TOOL_SEARCH,
            arguments={"query": default_query, "top_k": DEFAULT_SEARCH_TOP_K},
        )


def _extract_json(raw: str) -> dict | None:
    text = raw.strip()
    if text.startswith("```"):
        first_line = text.find("\n")
        if first_line != -1:
            text = text[first_line + 1 :]
        end_fence = text.rfind("```")
        if end_fence != -1:
            text = text[:end_fence]
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        payload = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None