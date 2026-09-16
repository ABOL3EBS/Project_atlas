# Atlas — Agentic Knowledge Assistant

Atlas turns your documents into an evidence-backed AI research assistant: document
ingestion, semantic retrieval, agentic tool selection, reranking, conversational
memory, citation-backed generation, execution tracing, and automated evaluation —
fully runnable locally for $0.

> **Status**: implementing **M0 + M1 + M2 + M3 + M4** (local RAG vertical slice,
> agent with tools and conversation memory, measured retrieval experiments). M5+
> unless explicitly instructed. See `IMPLEMENTATION_PLAN.md` for the plan and
> `ATLAS_PROJECT_SPEC.md` for the full spec.

## Stack

- Backend: Python 3.12 (uv), FastAPI, ChromaDB, Ollama (gemma2 / nomic-embed-text)
- Frontend: React + TypeScript + Vite + Tailwind (M7)
- Infra: Docker Compose (M8)

## Quick start (backend)

```bash
cd backend
cp .env.example .env   # adjust model names to your installed Ollama models
ollama serve
uv sync
uv run uvicorn app.main:app --port 8000
```

Verify: `GET http://localhost:8000/api/health`

### API

| Method | Path | Description |
|---|---|---|
| POST | `/api/documents/upload` | Upload PDF/markdown/txt (multipart, `knowledge_base_id` form field) |
| GET | `/api/documents` | List documents for a knowledge base |
| DELETE | `/api/documents/{id}` | Delete a document and its vectors |
| POST | `/api/chat` | Ask a question; SSE event stream (decision/tool_call/retrieval/token/done/error). Pass `conversation_id` to resume a thread |
| GET | `/api/conversations` | List conversations for a knowledge base |
| GET | `/api/conversations/{id}` | Conversation detail (KB-scoped) |
| GET | `/api/health` | Provider availability |

### Retrieval experiments (M4)

Every pipeline is measured against the real evaluation dataset
(`knowledge/eval/` corpus, 36 questions with hand-labelled `expected_sources`),
run locally with `nomic-embed-text` + ChromaDB and `gemma2:2b` for the LLM stages.
Results are written to `evaluation/results/`; nothing is estimated or fabricated.

```
Retrieval Experiment Results
Dataset: 36 questions · top_k=5 · chunk_size=250/overlap=25 · candidate pool=25

Pipeline                     Recall@5      MRR    Latency (ms)
-------------------------------------------------------------
Baseline                       1.0000   0.9583           17.7
+ Query Rewrite (LLM)          1.0000   0.9722          462.3
+ Reranking (BM25)             1.0000   1.0000           19.0
Multi-query → Dedup → Rerank   1.0000   1.0000          684.4
-------------------------------------------------------------
Latency is per-query wall time including every pipeline stage.
```

What the measurements say: all variants already retrieve every expected document at
top-5 (the corpus is small and topically clean). The difference is **ordering** —
baseline places the wrong related-topic document first in 3 of 36 questions, and
BM25 reranking fixes all three for ~1 ms of extra cost. The LLM stages (query
rewrite + multi-query) add 400–670 ms per query and produce no measurable benefit
on this dataset, so the production search tool stays on plain embedding search,
with reranking as the one adopted improvement. Reproduce with:

```bash
cd backend
uv run python ../evaluation/runners/run_retrieval.py
```

### Tests & lint

```bash
cd backend
uv run pytest
uvx ruff check .
```

Every chat SSE stream emits safe observable events (`decision`, `tool_call`,
`retrieval`, `memory`, `status`, `token`, `done`, `answer`, `error`) — never hidden
chain-of-thought. Atlas plans each turn (direct answer vs. one of four tools) and
only recalls selective, relevant conversation context.