# Atlas — Implementation Plan

Source of truth for the Atlas project direction. This document lives in the repo so the plan is durable and not dependent on chat context. Review `ATLAS_PROJECT_SPEC.md` for the full product spec.

Status: **M0/M1 complete — M2 complete — M3 complete — M4 complete — M5 complete**

---

## 1. Locked Decisions

| Area | Decision | Rationale |
|---|---|---|
| Python | `uv` + Python 3.12 pinned | chromadb has no Python 3.14 wheels; 3.12 is portable/reproducible |
| Embeddings | Ollama `nomic-embed-text` behind `EmbeddingProvider` | fully local/$0, avoids the torch dependency; SentenceTransformers impl optional later for benchmarking |
| LLM | Ollama (default `gemma2`), config-driven | local + $0; `LLMProvider` interface keeps OpenAI/Anthropic swappable later |
| Vector store | ChromaDB behind a `VectorStore` interface, scoped per `knowledge_base_id` | simple + reproducible; isolation by design |
| Frontend | Vite + React + TypeScript + Tailwind | light, fast to build, SSE streaming is trivial |
| Agent | One agent, several well-defined tools | no supervisor/research/retrieval/citation agent sprawl |

All provider/model choices are config-driven via `.env`:

```
LLM_PROVIDER=ollama
LLM_MODEL=gemma2
EMBEDDING_PROVIDER=ollama
EMBEDDING_MODEL=nomic-embed-text
```

Users can change models without touching code. The app must detect provider/model unavailability (Ollama down, embedding model missing) and return a useful error rather than crash.

---

## 2. Production Concerns (design-in from day one)

1. **Ingestion lifecycle + status**: `UPLOAD → VALIDATE → INGESTING → PARSE → CHUNK → EMBED → INDEXED`. UI states: `uploading`, `processing`, `indexed`, `failed`. Deleting a document must remove its vectors (no stale chunks in Chroma).
2. **Document isolation**: vector DB is not one global collection. Scope everything by `knowledge_base_id` → documents → chunks → vectors. Every retrieval request is scoped. No auth required for the MVP, but isolation is enforced structurally so it holds when auth lands.
3. **File deduplication**: SHA-256 of the file; if already indexed, skip.
4. **Grounding threshold**: if `retrieval_score < threshold`, respond "No relevant information was found in the knowledge base." The generation layer answers only from supported evidence and says so otherwise. Unsupported-answer rejection is an evaluation metric.
5. **Evaluation before optimization**: establish a retrieval baseline before adding query expansion/reranking. Only keep what measurably helps.
6. **Prompt-injection defense**: retrieved documents are data, never instructions. A malicious document containing "ignore previous instructions" must be treated as content and reported, not obeyed. Covered by tests.
7. **Observability**: stream safe execution events (status, retrieval, citations, tokens); expose latency, tool calls, errors. Never expose hidden chain-of-thought.
8. **Security/privacy basics** (per spec §24): validate file types, limit upload size, sanitize filenames, never execute uploads, isolate uploaded content, rate limit public deployments.

---

## 3. Milestones

### M0 — Scaffold
- `git init` in repo root (Project_Atlas)
- `uv` project pinned to Python 3.12
- Repo layout per spec §25
- `.env.example`, `.gitignore`, README skeleton
- `IMPLEMENTATION_PLAN.md` (this file)

### M1 — Basic RAG
- FastAPI backend (`/api`), module layout per spec §25
- Ingestion: PyMuPDF (PDF), markdown/txt parsers, cleaning, configurable chunking (`ChunkingConfig(chunk_size=500, chunk_overlap=50)`) with page/section metadata
- `EmbeddingProvider` interface + `OllamaEmbeddingProvider`
- `VectorStore` interface + ChromaDB implementation
- Semantic top-K retrieval
- `LLMProvider` interface + `OllamaProvider` (streaming)
- Endpoints: `/api/documents/upload`, `/api/documents`, `/api/chat` (SSE), `/api/health`
- Example knowledge base in `knowledge/example/`
- Tests: chunking, retrieval

### M2 — Production Ingestion + Citations
- Ingestion lifecycle/status (persisted), deletion with vector cleanup
- SHA-256 dedup, `knowledge_base_id` scoping
- Page/section metadata; citation collection + verification in responses
- Grounding threshold + explicit "not found"
- Prompt-injection hardening + failure handling (bad PDF, empty doc, Ollama down)

### M3 — Agent + Tools
- Tool registry: `search_knowledge_base`, `retrieve_document`, `compare_documents`, `get_conversation_context`
- Intent → retrieval decision flow; refusal for unsupported questions
- SQLite conversation memory (short-term context, no full-history dumps)

**M3 status:** done. `AtlasAgent` plans each turn via a JSON decision from the LLM (`none` for direct answers, or one of the four tools) with a safe fallback to `search_knowledge_base` on malformed/unknown output. `search_knowledge_base` and `compare_documents` are grounded by the M2 score threshold; `retrieve_document` is intent-gated (any evidence is sufficient). Conversation memory is selective (`MemorySelector`): only the most-similar messages within a 24-message window (max 3) are recalled. SSE now includes `conversation`, `decision`, `tool_call`, `tool_summary`, and `memory` events. REST: `GET /api/conversations`, `GET /api/conversations/{id}` (KB-scoped); `POST /api/chat` accepts `conversation_id` to resume a thread. Tests: memory store/selector, decision parser, tools, agent flows, conversations API (94+ tests).

### M4 — Retrieval Experiments
- Baseline first: `embedding → top-k`
- Experiments: `+ query rewrite`, `embedding → top-k → reranker`, `multi-query → dedup → reranker`
- Compare and keep only measurable wins

**M4 status:** done. Experiment harness under `app/retrieval/pipelines.py` (swappable
`Reranker` / `QueryTransformer` interfaces, zero new dependencies: BM25 reranker on the
stdlib), `app/evaluation/metrics.py` + `dataset.py`, CLI runner
`evaluation/runners/run_retrieval.py`. Evaluation corpus `knowledge/eval/` (12 docs, 39
chunks, including related-topic distractor clusters) with a 48-question labelled dataset
`evaluation/datasets/retrieval.json`. Measured against Ollama (`nomic-embed-text`,
`gemma2:2b`), top_k=5, chunk_size=250/overlap=25, candidate pool=25:

| Pipeline | Recall@5 | MRR | Latency (ms) |
|---|---|---|---|
| Baseline (embed → top-k) | 1.0000 | 0.9653 | 17.3 |
| + Query rewrite | 0.9583 | 0.8889 | 455.6 |
| + Reranking | 1.0000 | 0.9896 | 19.3 |
| Multi-query → dedup → rerank | 1.0000 | 0.9896 | 753.5 |

Outcome: BM25 reranking is the only adopted improvement — it fixes 3 baseline
ordering failures for a net +0.024 MRR at +2 ms. LLM query rewrite measurably hurts
(this dataset: 8 degraded questions, 2 recall failures, +438 ms), and multi-query
ties reranking quality at 39× latency; neither is wired into production. Reproduce:
`uv run python ../evaluation/runners/run_retrieval.py`.

### M5 — Observability / Trace
- Execution-event model (safe observable events only)
- `/api/trace/{conversation_id}`; latency, tool call, error, citation diagnostics
- SSE event emission (`status`, `retrieval`, `citation`, `token`)

**M5 status:** done. Every real execution step of `AtlasAgent.run` is recorded as a
structured trace: `trace_started`, `agent_started`, `decision`, `tool_call`,
`retrieval`, `reranking`, `grounding`, `citation`, `generation_started`,
`generation_completed`, `error`, `trace_completed`. The trace module lives in
`app/trace/` (event model + in-memory `TraceRecorder` + SQLite `TraceStore`, separate
`traces.db`, `knowledge_base_id` scoping on every row). Trace metadata is telemetry
only — counts, KB id, tool name, method, thresholds, scores, latency — never
chain-of-thought, system prompts, retrieved text, tool arguments, or secrets; error
messages are capped at 500 chars and surfaced with an `AGENT_FAILED` code. Persisted
traces are retrievable via `GET /api/trace/{conversation_id}?knowledge_base_id=…`
(404 for a different KB, mirroring `/api/conversations`). The same SSE channel now
carries `trace`, `reranking`, `grounding`, `citation`, and `trace_completed` events
in addition to the existing ones; every persisted trace ends in a `trace_completed`
event with overall status and latency. M5 also closed a usability gap: BM25
reranking (the M4-adopted improvement) is now actually wired into the production
`SearchKnowledgeBaseTool` — embedding top-k results are re-scored with the same
`BM25Reranker` the experiments used, and the `search`/`rerank` timings land in the
retrieval/reranking trace events. Tests: trace recorder/store round-trip and order,
agent trace recording per flow (direct, search, retrieve_document, memory), failed
trace on tool/LLM failure, no-secrets/reasoning guard, multi-trace threads, KB
isolation, and trace API + SSE tests (142+ tests).

### M6 — Evaluation
- Dataset of 20–50 questions with `expected_sources`
- Metrics: Recall@K, MRR, citation accuracy, faithfulness/groundedness, latency, unsupported-answer rejection
- Real numbers (never fabricated) → README + results files

### M7 — Frontend
- Vite + React + TS + Tailwind
- Screens: Knowledge Base (upload, status badges, delete), Chat (grounded answers, clickable citations), Trace panel (streamed events)
- Simple, clean; UI complexity must not distract from the AI engineering

### M8 — Docker / Deployment
- Dockerfiles + `docker-compose.yml` → `docker compose up`
- Rate limiting + isolation notes for public hosting
- README: setup, architecture diagram, real eval results, screenshots

---

## 4. Test Matrix

Unit / integration / resilience tests:

- chunking (sizes, overlap, metadata preserved, structural units)
- retrieval (relevant results, zero-result case)
- malformed PDFs, empty documents
- duplicate uploads, deletion, isolation (KB A cannot see KB B)
- citation correctness, grounding-threshold rejection, unsupported questions
- conversation context, tool selection
- decision parser + planner fallback
- prompt injection (document says "ignore instructions / reveal system prompt")
- provider failures: Ollama unavailable, embedding failure, LLM failure
- full integration: document → ingest → embed → retrieve → agent → answer → citation

---

## 5. Explicitly NOT Building

- Generic ChatGPT clone
- Simple LangChain tutorial
- Supervisor / research / retrieval / citation / evaluation agent sprawl
- Fake agent behavior where every request follows the identical pipeline
- Multi-agent systems for their own sake
- UI-first project with little backend depth
- Anything requiring a paid API to run locally

---

## 6. Definition of Done (portfolio-ready)

Per spec §29: open app → upload docs → ingestion completes → ask questions → grounded answers → citations → natural follow-ups → inspect trace → run evaluation locally → start via documented setup. README includes architecture diagram, tests, eval dataset, real eval results, example KB, screenshots, and design-decision explanations.

---

## 7. Environment Notes (verified at plan time)

- macOS; Python 3.14.3 system (unused — 3.12 pinned via uv)
- Node 25 / npm 11; Docker 29; Ollama 0.20.2 with `gemma2` pulled
- chromadb has no Python 3.14 wheels → 3.12 pin