import json

from app.agent.decision import (
    DIRECT,
    TOOL_COMPARE,
    TOOL_MEMORY,
    TOOL_RETRIEVE,
    TOOL_SEARCH,
    DecisionParser,
    PlannedAction,
    build_planner_system,
)
from app.agent.registry import ToolRegistry
from app.agent.tools import (
    CompareDocumentsTool,
    GetConversationContextTool,
    RetrieveDocumentTool,
    SearchKnowledgeBaseTool,
)
from tests.conftest import FakeVectorStore


def make_registry() -> ToolRegistry:
    return ToolRegistry(
        [
            SearchKnowledgeBaseTool(object()),
            RetrieveDocumentTool(object(), FakeVectorStore()),
            CompareDocumentsTool(object()),
            GetConversationContextTool(),
        ]
    )


def test_parser_accepts_direct_answer():
    parser = DecisionParser(make_registry())
    action = parser.parse(json.dumps({"tool": "none", "arguments": {}}), default_query="hi")
    assert action == PlannedAction(tool=None, arguments={})


def test_parser_accepts_real_tool():
    parser = DecisionParser(make_registry())
    raw = json.dumps(
        {"tool": TOOL_SEARCH, "arguments": {"query": "requirements", "top_k": 4}}
    )
    action = parser.parse(raw, default_query="ignored")
    assert action.tool == TOOL_SEARCH
    assert action.arguments == {"query": "requirements", "top_k": 4}


def test_parser_falls_back_to_search_on_malformed_json():
    parser = DecisionParser(make_registry())
    action = parser.parse("not a decision at all", default_query="orig question")
    assert action.tool == TOOL_SEARCH
    assert action.arguments["query"] == "orig question"
    assert action.arguments["top_k"] == 4


def test_parser_reads_json_inside_code_fence():
    parser = DecisionParser(make_registry())
    raw = '```json\n{"tool": "none", "arguments": {}}\n```'
    action = parser.parse(raw, default_query="x")
    assert action.tool is None


def test_parser_falls_back_on_unknown_tool():
    parser = DecisionParser(make_registry())
    raw = json.dumps({"tool": "fake_tool", "arguments": {}})
    action = parser.parse(raw, default_query="q")
    assert action.tool == TOOL_SEARCH


def test_parser_falls_back_on_missing_required_argument():
    parser = DecisionParser(make_registry())
    raw = json.dumps({"tool": TOOL_RETRIEVE, "arguments": {}})
    action = parser.parse(raw, default_query="q")
    assert action.tool == TOOL_SEARCH


def test_parser_falls_back_on_wrong_argument_type():
    parser = DecisionParser(make_registry())
    raw = json.dumps(
        {"tool": TOOL_COMPARE, "arguments": {"documents": "not-a-list", "question": "q"}}
    )
    action = parser.parse(raw, default_query="q")
    assert action.tool == TOOL_SEARCH


def test_parser_fills_missing_query_with_default():
    parser = DecisionParser(make_registry())
    raw = json.dumps({"tool": TOOL_SEARCH, "arguments": {"top_k": 2}})
    action = parser.parse(raw, default_query="defaulted query")
    assert action.arguments["query"] == "defaulted query"


def test_planner_system_lists_documents_and_tools():
    regex = make_registry()
    system = build_planner_system(["a.pdf", "b.pdf"], regex)
    assert ["a.pdf", "b.pdf"]
    for tool in (
        TOOL_SEARCH,
        TOOL_RETRIEVE,
        TOOL_COMPARE,
        TOOL_MEMORY,
        DIRECT,
    ):
        assert f'"{tool}"' in system
    assert "a.pdf" in system
    assert "b.pdf" in system
    assert "top_k" in system