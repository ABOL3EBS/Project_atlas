import logging

from app.llm.base import LLMProvider
from app.memory.conversation_store import ConversationStore
from app.memory.selector import MemorySelector
from app.services.document_store import DocumentStore
from app.trace import TraceEventType, TraceRecorder, now_ms
from app.trace.store import TraceStore

from .base import ToolContext
from .decision import (
    TOOL_MEMORY,
    TOOL_RETRIEVE,
    TOOL_SEARCH,
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

logger = logging.getLogger("atlas.agent")


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
        trace_store: TraceStore | None = None,
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
        self._trace_store = trace_store

    async def run(self, knowledge_base_id: str, question: str, conversation_id: str = None):
        trace = TraceRecorder(
            knowledge_base_id=knowledge_base_id,
            conversation_id=conversation_id,
            question=question,
        )
        try:
            async for event in self._run_inner(knowledge_base_id, question, conversation_id, trace):
                yield event
        except Exception as error:
            trace.complete(status="failed")
            trace.error(component="agent", code="AGENT_FAILED", message=str(error))
            yield {"type": "error", "message": f"Atlas failed: {error}"}
            yield self._trace_completed_event(trace)
        else:
            trace.complete(status="completed")
            yield self._trace_completed_event(trace)
        finally:
            self._persist_trace(trace)

    async def _run_inner(
        self, knowledge_base_id, question, conversation_id, trace: TraceRecorder
    ):
        conversation_id = await self._ensure_conversation(knowledge_base_id, conversation_id)
        trace.conversation_id = conversation_id
        trace.record(TraceEventType.TRACE_STARTED, status="started")
        trace.record(
            TraceEventType.AGENT_STARTED,
            metadata={"knowledge_base_id": knowledge_base_id, "question_length": len(question)},
        )
        yield {
            "type": "conversation",
            "conversation_id": conversation_id,
            "knowledge_base_id": knowledge_base_id,
        }
        yield {
            "type": "trace",
            "trace_id": trace.trace_id,
            "conversation_id": conversation_id,
            "knowledge_base_id": knowledge_base_id,
        }

        docs = self._indexed_documents(knowledge_base_id)
        start = now_ms()
        plan = await self._plan(question, docs)
        trace.record(
            TraceEventType.DECISION,
            latency_ms=now_ms() - start,
            metadata={
                "source": "tool" if plan.uses_tool else "direct",
                "tool": plan.tool,
            },
        )

        yield {
            "type": "decision",
            "source": "tool" if plan.uses_tool else "direct",
            "tool": plan.tool,
            "arguments": plan.arguments,
        }

        answer = {"text": ""}
        if plan.tool == TOOL_MEMORY:
            async for event in self._memory_flow(
                plan, knowledge_base_id, question, docs, conversation_id, answer, trace
            ):
                yield event
        elif plan.tool is None:
            async for event in self._direct_flow(question, answer, trace):
                yield event
        else:
            async for event in self._tool_flow(
                plan, knowledge_base_id, question, docs, answer, trace
            ):
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

    async def _direct_flow(self, question: str, answer: dict, trace: TraceRecorder) -> None:
        yield {"type": "status", "stage": "generating"}
        trace.record(
            TraceEventType.GENERATION_STARTED,
            status="started",
            metadata=self._llm_profile(),
        )
        answer_text = ""
        with trace.span(TraceEventType.GENERATION_COMPLETED, metadata=self._llm_profile()):
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
        trace: TraceRecorder,
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
        result = None
        with trace.span(
            TraceEventType.TOOL_CALL,
            metadata={"tool": plan.tool, "knowledge_base_id": knowledge_base_id},
        ):
            result = await self._registry.get(plan.tool).execute(context, plan.arguments)
        evidence = result.evidence
        self._record_retrieval(
            trace,
            knowledge_base_id,
            candidates=result.candidates,
            returned=len(evidence),
            latency_ms=result.timings.get("search"),
        )
        yield {
            "type": "retrieval",
            "count": len(evidence),
            "chunks": chunk_briefs(evidence),
        }
        if result.timings.get("rerank") is not None:
            rerank_ms = result.timings["rerank"]
            trace.record(
                TraceEventType.RERANKING,
                latency_ms=rerank_ms,
                metadata={
                    "method": "bm25",
                    "input_count": result.candidates,
                    "output_count": len(evidence),
                },
            )
            yield {
                "type": "reranking",
                "method": "bm25",
                "input_count": result.candidates,
                "output_count": len(evidence),
                "latency_ms": round(rerank_ms, 3),
            }
        if result.summary:
            yield {"type": "tool_summary", "tool": plan.tool, "summary": result.summary}

        if not self._evidence_sufficient(plan.tool, evidence):
            self._record_grounding(trace, plan.tool, evidence, sufficient=False)
            yield self._grounding_event(
                plan.tool, sufficient=False, evidence=evidence
            )
            yield {"type": "answer", "text": NOT_FOUND_MESSAGE}
            answer["text"] = NOT_FOUND_MESSAGE
            return

        self._record_grounding(trace, plan.tool, evidence, sufficient=True)
        yield self._grounding_event(plan.tool, sufficient=True, evidence=evidence)
        citations = verify_citations(build_citations(evidence), evidence)
        yield self._citation_event(trace, citations)

        prompt = build_prompt(question, evidence)
        yield {"type": "status", "stage": "generating"}
        trace.record(
            TraceEventType.GENERATION_STARTED,
            status="started",
            metadata=self._llm_profile(),
        )
        answer_text = ""
        with trace.span(TraceEventType.GENERATION_COMPLETED, metadata=self._llm_profile()):
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
        trace: TraceRecorder,
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
        memory_result = None
        with trace.span(
            TraceEventType.TOOL_CALL,
            metadata={"tool": TOOL_MEMORY, "knowledge_base_id": knowledge_base_id},
        ):
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
        start = now_ms()
        chunks = self._retriever.search(knowledge_base_id, search_query)
        self._record_retrieval(
            trace,
            knowledge_base_id,
            candidates=len(chunks),
            returned=len(chunks),
            latency_ms=now_ms() - start,
        )
        yield {
            "type": "retrieval",
            "count": len(chunks),
            "chunks": chunk_briefs(chunks),
        }

        if chunks and _has_grounded_evidence(chunks, self._grounding_threshold):
            self._record_grounding(trace, TOOL_SEARCH, chunks, sufficient=True)
            yield self._grounding_event(TOOL_SEARCH, sufficient=True, evidence=chunks)
            citations = verify_citations(build_citations(chunks), chunks)
            yield self._citation_event(trace, citations)
            prompt = build_prompt_with_memory(question, chunks, memory_messages)
            yield {"type": "status", "stage": "generating"}
            trace.record(
                TraceEventType.GENERATION_STARTED,
                status="started",
                metadata=self._llm_profile(),
            )
            answer_text = ""
            with trace.span(TraceEventType.GENERATION_COMPLETED, metadata=self._llm_profile()):
                async for token in self._llm.stream(prompt, system=SYSTEM_PROMPT):
                    yield {"type": "token", "text": token}
                    answer_text += token
            yield {"type": "done", "citations": [c.to_dict() for c in citations]}
            answer["text"] = answer_text
            return

        self._record_grounding(trace, TOOL_SEARCH, chunks, sufficient=False)
        yield self._grounding_event(TOOL_SEARCH, sufficient=False, evidence=chunks)

        if memory_messages:
            async for event in self._answer_from_memory(memory_messages, question, answer, trace):
                yield event
            return

        yield {"type": "answer", "text": NOT_FOUND_MESSAGE}
        answer["text"] = NOT_FOUND_MESSAGE

    async def _answer_from_memory(
        self, messages: list[dict], question: str, answer: dict, trace: TraceRecorder
    ) -> None:
        transcript = "\n".join(f"{m['role']}: {m['content']}" for m in messages)
        prompt = (
            f"Relevant earlier conversation:\n{transcript}\n\n"
            f"Question: {question}\n\n"
            "Answer based only on the conversation context above. "
            "Do not invent new information; if the context is insufficient say so."
        )
        yield {"type": "status", "stage": "generating"}
        trace.record(
            TraceEventType.GENERATION_STARTED,
            status="started",
            metadata=self._llm_profile(),
        )
        answer_text = ""
        with trace.span(TraceEventType.GENERATION_COMPLETED, metadata=self._llm_profile()):
            async for token in self._llm.stream(prompt, system=DIRECT_ANSWER_PROMPT):
                yield {"type": "token", "text": token}
                answer_text += token
        yield {"type": "done", "citations": []}
        answer["text"] = answer_text

    # ── Trace helpers ─────────────────────────────────────────────────

    def _llm_profile(self) -> dict:
        return {
            "provider": getattr(self._llm, "provider_name", None),
            "model": getattr(self._llm, "model_name", None),
        }

    def _record_retrieval(
        self,
        trace: TraceRecorder,
        knowledge_base_id: str,
        *,
        candidates: int | None,
        returned: int,
        latency_ms: float | None,
    ) -> None:
        trace.record(
            TraceEventType.RETRIEVAL,
            latency_ms=latency_ms,
            metadata={
                "knowledge_base_id": knowledge_base_id,
                "candidates": candidates,
                "returned": returned,
            },
        )

    def _record_grounding(
        self,
        trace: TraceRecorder,
        tool: str,
        evidence,
        *,
        sufficient: bool,
    ) -> None:
        if tool == TOOL_RETRIEVE:
            rule, threshold = "any_evidence", None
        else:
            rule, threshold = "threshold", self._grounding_threshold
        score = max((chunk.score for chunk in evidence), default=None)
        trace.record(
            TraceEventType.GROUNDING,
            status="passed" if sufficient else "rejected",
            metadata={"rule": rule, "score": score, "threshold": threshold},
        )

    def _citation_event(self, trace: TraceRecorder, citations) -> dict:
        for citation in citations:
            trace.record(
                TraceEventType.CITATION,
                metadata={
                    "chunk_id": citation.chunk_id,
                    "document_id": citation.document_id,
                    "document_name": citation.document_name,
                    "page": citation.page,
                    "section": citation.section,
                },
            )
        return {
            "type": "citation",
            "status": "verified",
            "count": len(citations),
            "citations": [citation.to_dict() for citation in citations],
        }

    def _grounding_event(self, tool: str, *, sufficient: bool, evidence) -> dict:
        if tool == TOOL_RETRIEVE:
            rule, threshold = "any_evidence", None
        else:
            rule, threshold = "threshold", self._grounding_threshold
        score = max((chunk.score for chunk in evidence), default=None)
        return {
            "type": "grounding",
            "status": "passed" if sufficient else "rejected",
            "rule": rule,
            "score": round(score, 4) if score is not None else None,
            "threshold": threshold,
            "evidence_count": len(evidence),
        }

    def _persist_trace(self, trace: TraceRecorder) -> None:
        if not self._trace_store:
            return
        try:
            self._trace_store.save_trace(trace)
        except Exception:
            logger.warning("failed to persist trace %s", trace.trace_id, exc_info=True)

    def _trace_completed_event(self, trace: TraceRecorder) -> dict:
        return {
            "type": "trace_completed",
            "trace_id": trace.trace_id,
            "conversation_id": trace.conversation_id,
            "status": trace.status,
            "latency_ms": round(trace.total_latency_ms, 3) if trace.total_latency_ms else None,
        }

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