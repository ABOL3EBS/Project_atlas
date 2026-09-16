from app.llm.base import LLMProvider
from app.memory.conversation_store import ConversationStore
from app.memory.selector import MemorySelector
from app.services.document_store import DocumentStore

from .base import ToolContext
from .decision import (
    TOOL_MEMORY,
    TOOL_RETRIEVE,
    DecisionParser,
    PlannedAction,
    build_planner_system,
)
from .grounding import (
    DIRECT_ANSWER_PROMPT,
    NOT_FOUND_MESSAGE,
    SYSTEM_PROMPT,
    build_citations,
    build_prompt,
    build_prompt_with_memory,
    chunk_briefs,
    verify_citations,
)
from .registry import ToolRegistry
from .tools import (
    CompareDocumentsTool,
    GetConversationContextTool,
    RetrieveDocumentTool,
    SearchKnowledgeBaseTool,
)


def default_registry(retriever, vector_store) -> ToolRegistry:
    return ToolRegistry(
        [
            SearchKnowledgeBaseTool(retriever),
            RetrieveDocumentTool(retriever, vector_store),
            CompareDocumentsTool(retriever),
            GetConversationContextTool(),
        ]
    )


class AtlasAgent:
    def __init__(
        self,
        *,
        retriever,
        llm_provider: LLMProvider,
        vector_store,
        document_store: DocumentStore | None = None,
        conversation_store: ConversationStore | None = None,
        memory_selector: MemorySelector | None = None,
        registry: ToolRegistry | None = None,
        grounding_threshold: float = 0.45,
    ):
        self._retriever = retriever
        self._llm = llm_provider
        self._vector_store = vector_store
        self._document_store = document_store
        self._conversation_store = conversation_store
        self._memory_selector = memory_selector
        self._registry = registry or default_registry(retriever, vector_store)
        self._parser = DecisionParser(self._registry)
        self._grounding_threshold = grounding_threshold

    async def run(self, knowledge_base_id: str, question: str, conversation_id: str = None):
        try:
            async for event in self._run_inner(knowledge_base_id, question, conversation_id):
                yield event
        except Exception as error:
            yield {"type": "error", "message": f"Atlas failed: {error}"}

    async def _run_inner(self, knowledge_base_id, question, conversation_id):
        conversation_id = await self._ensure_conversation(knowledge_base_id, conversation_id)
        yield {
            "type": "conversation",
            "conversation_id": conversation_id,
            "knowledge_base_id": knowledge_base_id,
        }

        docs = self._indexed_documents(knowledge_base_id)
        plan = await self._plan(question, docs)

        yield {
            "type": "decision",
            "source": "tool" if plan.uses_tool else "direct",
            "tool": plan.tool,
            "arguments": plan.arguments,
        }

        answer = {"text": ""}
        if plan.tool == TOOL_MEMORY:
            async for event in self._memory_flow(
                plan, knowledge_base_id, question, docs, conversation_id, answer
            ):
                yield event
        elif plan.tool is None:
            async for event in self._direct_flow(question, answer):
                yield event
        else:
            async for event in self._tool_flow(plan, knowledge_base_id, question, docs, answer):
                yield event

        if self._conversation_store and conversation_id and answer["text"]:
            self._conversation_store.append_message(conversation_id, "user", question)
            self._conversation_store.append_message(conversation_id, "assistant", answer["text"])

    # ── Planning ──────────────────────────────────────────────────────

    async def _plan(self, question: str, documents: list[dict]) -> PlannedAction:
        system = build_planner_system(
            [document["name"] for document in documents], self._registry
        )
        raw = await self._llm.generate(question, system=system, json_mode=True)
        return self._parser.parse(raw, default_query=question)

    # ── Direct answer ─────────────────────────────────────────────────

    async def _direct_flow(self, question: str, answer: dict) -> None:
        yield {"type": "status", "stage": "generating"}
        answer_text = ""
        async for token in self._llm.stream(question, system=DIRECT_ANSWER_PROMPT):
            yield {"type": "token", "text": token}
            answer_text += token
        yield {"type": "done", "citations": []}
        answer["text"] = answer_text

    # ── Tool execution ────────────────────────────────────────────────

    async def _tool_flow(
        self,
        plan: PlannedAction,
        knowledge_base_id: str,
        question: str,
        docs: list[dict],
        answer: dict,
    ) -> None:
        yield {
            "type": "tool_call",
            "tool": plan.tool,
            "arguments": plan.arguments,
        }
        context = ToolContext(
            knowledge_base_id=knowledge_base_id,
            retriever=self._retriever,
            vector_store=self._vector_store,
            documents=docs,
        )
        result = await self._registry.get(plan.tool).execute(context, plan.arguments)
        evidence = result.evidence
        yield {
            "type": "retrieval",
            "count": len(evidence),
            "chunks": chunk_briefs(evidence),
        }
        if result.summary:
            yield {"type": "tool_summary", "tool": plan.tool, "summary": result.summary}

        if not self._evidence_sufficient(plan.tool, evidence):
            yield {"type": "answer", "text": NOT_FOUND_MESSAGE}
            answer["text"] = NOT_FOUND_MESSAGE
            return

        citations = verify_citations(build_citations(evidence), evidence)
        prompt = build_prompt(question, evidence)

        yield {"type": "status", "stage": "generating"}
        answer_text = ""
        async for token in self._llm.stream(prompt, system=SYSTEM_PROMPT):
            yield {"type": "token", "text": token}
            answer_text += token
        yield {"type": "done", "citations": [citation.to_dict() for citation in citations]}
        answer["text"] = answer_text

    # ── Conversation memory flow ──────────────────────────────────────

    async def _memory_flow(
        self,
        plan: PlannedAction,
        knowledge_base_id: str,
        question: str,
        docs: list[dict],
        conversation_id: str,
        answer: dict,
    ) -> None:
        yield {
            "type": "tool_call",
            "tool": TOOL_MEMORY,
            "arguments": plan.arguments,
        }
        context = ToolContext(
            knowledge_base_id=knowledge_base_id,
            retriever=self._retriever,
            vector_store=self._vector_store,
            documents=docs,
            conversation_id=conversation_id,
            memory_store=self._conversation_store,
            memory_selector=self._memory_selector,
        )
        memory_result = await self._registry.get(TOOL_MEMORY).execute(context, plan.arguments)
        memory_messages = _parse_memory_blocks(memory_result.summary or "")
        yield {
            "type": "memory",
            "count": len(memory_messages),
            "messages": [
                {"role": message["role"], "content": message["content"][:200]}
                for message in memory_messages
            ],
        }

        search_query = plan.arguments.get("question", question)
        chunks = self._retriever.search(knowledge_base_id, search_query)
        yield {
            "type": "retrieval",
            "count": len(chunks),
            "chunks": chunk_briefs(chunks),
        }

        if chunks and _has_grounded_evidence(chunks, self._grounding_threshold):
            citations = verify_citations(build_citations(chunks), chunks)
            prompt = build_prompt_with_memory(question, chunks, memory_messages)
            yield {"type": "status", "stage": "generating"}
            answer_text = ""
            async for token in self._llm.stream(prompt, system=SYSTEM_PROMPT):
                yield {"type": "token", "text": token}
                answer_text += token
            yield {"type": "done", "citations": [c.to_dict() for c in citations]}
            answer["text"] = answer_text
            return

        if memory_messages:
            async for event in self._answer_from_memory(memory_messages, question, answer):
                yield event
            return

        yield {"type": "answer", "text": NOT_FOUND_MESSAGE}
        answer["text"] = NOT_FOUND_MESSAGE

    async def _answer_from_memory(self, messages: list[dict], question: str, answer: dict) -> None:
        transcript = "\n".join(f"{m['role']}: {m['content']}" for m in messages)
        prompt = (
            f"Relevant earlier conversation:\n{transcript}\n\n"
            f"Question: {question}\n\n"
            "Answer based only on the conversation context above. "
            "Do not invent new information; if the context is insufficient say so."
        )
        yield {"type": "status", "stage": "generating"}
        answer_text = ""
        async for token in self._llm.stream(prompt, system=DIRECT_ANSWER_PROMPT):
            yield {"type": "token", "text": token}
            answer_text += token
        yield {"type": "done", "citations": []}
        answer["text"] = answer_text

    # ── Helpers ───────────────────────────────────────────────────────

    def _evidence_sufficient(self, tool: str, evidence) -> bool:
        if tool == TOOL_RETRIEVE:
            return len(evidence) > 0
        return _has_grounded_evidence(evidence, self._grounding_threshold)

    def _indexed_documents(self, knowledge_base_id: str) -> list[dict]:
        if not self._document_store:
            return []
        return [
            document
            for document in self._document_store.list(knowledge_base_id)
            if document.get("status") == "indexed"
        ]

    async def _ensure_conversation(
        self, knowledge_base_id: str, conversation_id: str | None
    ) -> str | None:
        if not self._conversation_store:
            return None
        return self._conversation_store.ensure_conversation(knowledge_base_id, conversation_id)


def _has_grounded_evidence(chunks, threshold: float) -> bool:
    if not chunks:
        return False
    return max(chunk.score for chunk in chunks) >= threshold


def _parse_memory_blocks(summary: str) -> list[dict]:
    messages = []
    for line in summary.split("\n"):
        line = line.strip()
        if not line:
            continue
        for prefix in ("user:", "assistant:"):
            if line.lower().startswith(prefix):
                messages.append({"role": prefix[:-1], "content": line[len(prefix):].strip()})
                break
    return messages