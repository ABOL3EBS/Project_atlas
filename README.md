# Atlas — Agentic Knowledge Assistant

Atlas turns your documents into an evidence-backed AI research assistant: document
ingestion, semantic retrieval, agentic tool selection, reranking, conversational
memory, citation-backed generation, execution tracing, and automated evaluation —
fully runnable locally for $0.

> **Status**: implementing **M0 + M1 + M2** (local RAG vertical slice with grounding,
> citation verification, prompt-injection defense). See `IMPLEMENTATION_PLAN.md` for
> the plan and `ATLAS_PROJECT_SPEC.md` for the full spec.

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
| POST | `/api/chat` | Ask a question; SSE event stream (retrieval/token/done) |
| GET | `/api/health` | Provider availability |

### Tests & lint

```bash
cd backend
uv run pytest
uvx ruff check .
```

Every chat SSE stream emits safe observable events (`retrieval`, `status`, `token`,
`done`, `error`) — not hidden chain-of-thought.