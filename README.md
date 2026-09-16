# Atlas — Agentic Knowledge Assistant

Atlas turns your documents into an evidence-backed AI research assistant: document
ingestion, semantic retrieval, agentic tool selection, reranking, conversational
memory, citation-backed generation, execution tracing, and automated evaluation —
fully runnable locally for $0.

> **Status**: **M0–M6 complete** (local RAG vertical slice, agent with tools and
> conversation memory, measured retrieval experiments, execution trace/observability,
> answer-level evaluation + grounding threshold calibration). M7+ not started; only on
> explicit instruction. See `IMPLEMENTATION_PLAN.md` for the plan and
> `ATLAS_PROJECT_SPEC.md` for the spec.

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
| POST | `/api/chat` | Ask a question; SSE event stream (decision/tool_call/retrieval/token/done/error/trace/…). Pass `conversation_id` to resume a thread |
| GET | `/api/conversations` | List conversations for a knowledge base |
| GET | `/api/conversations/{id}` | Conversation detail (KB-scoped) |
| GET | `/api/trace/{conversation_id}` | Execution traces for a conversation (KB-scoped, `knowledge_base_id` query param) |
| GET | `/api/health` | Provider availability |

### Retrieval experiments (M4)

Every pipeline is measured against the real evaluation dataset
(`knowledge/eval/` corpus: 12 documents, 39 chunks, 48 questions with hand-labelled
`expected_sources`), run locally with `nomic-embed-text` + ChromaDB and `gemma2:2b`
for the LLM stages. Results are written to `evaluation/results/`; nothing is
estimated or fabricated.

```
Retrieval Experiment Results
Dataset: 48 questions · top_k=5 · chunk_size=250/overlap=25 · candidate pool=25

Pipeline                     Recall@5      MRR    Latency (ms)
-------------------------------------------------------------
Baseline                       1.0000   0.9653           17.3
+ Query Rewrite (LLM)          0.9583   0.8889          455.6
+ Reranking (BM25)             1.0000   0.9896           19.3
Multi-query → Dedup → Rerank   1.0000   0.9896          753.5
-------------------------------------------------------------
Latency is per-query wall time including every pipeline stage.
```

What the measurements say:

- **BM25 reranking is the adopted improvement.** Baseline mis-orders related-topic
  documents in 3 of 48 questions; reranking fixes all three (it introduces one
  ordering regression elsewhere) for a net **+0.024 MRR** at +2 ms per query.
- **LLM query rewrite measurably hurts retrieval here.** It degrades 8 of 48
  questions and, on two of them, pulls the search into entirely unrelated documents
  so the expected source drops out of top-5 entirely (Recall@5 1.0 → 0.9583, MRR
  0.9653 → 0.8889) at +438 ms per query. Not adopted.
- **Multi-query ties reranking on quality** (same BM25 reranker) but costs 39× the
  latency of the baseline. Not adopted on this dataset.

So production search stays on plain embedding search with BM25 reranking behind the
swappable `Reranker` interface (and, since M5, the rerank actually runs in the
production `SearchKnowledgeBaseTool`). Reproduce with:

```bash
cd backend
uv run python ../evaluation/runners/run_retrieval.py
```

### Execution traces (M5)

Every real execution step of a chat turn is recorded as a trace and persisted to
`backend/data/traces.db` (SQLite, one store per DB, KB-scoped):

- **Event types**: `trace_started`, `agent_started`, `decision`, `tool_call`,
  `retrieval`, `reranking`, `grounding`, `citation`, `generation_started`,
  `generation_completed`, `error`, `trace_completed`.
- **Retrieval**: recorded counts are real (`candidates` vs. `returned`) and so are
  the `search`/`rerank` timings; the `reranking` event fires only when a rerank ran
  (search tool), never for `retrieve_document`.
- **Grounding**: `passed`/`rejected` with the rule (`threshold` for search/compare
  tools, `any_evidence` for retrieve_document/tool), the top evidence score, and the
  threshold that decided it.
- **Citations**: one event per verified citation (chunk id, document name, page,
  section).
- **Security boundary**: traces expose telemetry only — counts, KB id, tool name,
  method, scores, latency. They never include retrieved document text, the user
  query, tool arguments, model reasoning, system prompts, or provider secrets.
  Error events carry a safe message (capped at 500 chars).

Retrieve traces for a conversation (404 if you use the wrong knowledge base):

```bash
curl "http://localhost:8000/api/trace/<conversation_id>?knowledge_base_id=default"
```

Traces also stream live on the chat SSE channel (`trace`, `reranking`, `grounding`,
`citation`, `trace_completed` events) alongside the existing observability events.

### Answer evaluation (M6)

M6 extends measurement from retrieval (M4) to the full generated answer. The answer
runner (`evaluation/runners/run_answer_eval.py`) drives the real `AtlasAgent` over 68
labelled questions — the 48 supported questions from M4 plus 20 out-of-domain
unsupported questions (`evaluation/datasets/answer.json`, expected answer = NOT_FOUND) —
against the same 12-doc corpus, and measures rejection, citations, judge-based
faithfulness, and full-turn latency. Results are written to `evaluation/results/`
(nothing estimated).

Measured E2E at the then-current default threshold 0.45 (`evaluation/results/`):

```
unsupported rejection rate : 0.2000  (4/20)
unsupported answered rate  : 0.8000  (16/20 → hallucination risk)
supported answer rate      : 0.9792  (47/48)
citation precision         : 0.5952   coverage 0.9524
faithfulness (judge, n=42) : 0.9048
latency mean/med/p90       : 6326 / 6150 / 8340 ms
```

The headline deliverable is the **grounding-threshold calibration** — the same real
search scores, expressed as an accept/reject curve:

```
threshold              0.35    0.40    0.45    0.50    0.55    0.60    0.65
true_accept (48)       1.0000  1.0000  1.0000  1.0000  1.0000  1.0000  0.7500
false_accept (20)      1.0000  1.0000  0.9500  0.7500  0.2500  0.0000  0.0000
```

The **gate calibration** (isolated single-search measurement) is well-separated at
**0.60** — every supported question scores ≥ 0.604, every unsupported one ≤ 0.587 —
so the default threshold moved **0.45 → 0.60** (only after measurement, per the
M4/M5 contract). Note the sample: "0.00" at 0.60 means **0/20 observed**, not a hard
guarantee — the cliff from 0.55 to 0.60 is one grid step wide on 20 questions, and a
21st adversarial query could land in the 0.587–0.60 gap. Effect on the same real
recordings: gate false-accepts 19/20 → 0/20, supported acceptance unchanged 48/48,
projected E2E unsupported rejection 0.20 → 0.55.

Keep the two tables separate: **threshold calibration fixes the gate — it does not fix
the planner.** End-to-end rejection was 0.20 because the planner answered 16/20
unsupported questions without ever searching, so the gate was never reached for most of
them; leaving that leak open is a follow-up milestone item (planner routing), not
something folded into M6. A separate known gap: citation precision 0.595 (~40% of cited
documents don't precision-match) is measured and tracked, not silently fixed.

Reproduce:

```bash
cd backend
uv run python ../evaluation/runners/run_retrieval.py   # M4
uv run python ../evaluation/runners/run_answer_eval.py  # M6
```

### Tests & lint

```bash
cd backend
uv run pytest
uvx ruff check .
```

Every chat SSE stream emits safe observable events (`conversation`, `decision`,
`tool_call`, `retrieval`, `reranking`, `grounding`, `citation`, `memory`, `status`,
`token`, `done`, `answer`, `trace`, `trace_completed`, `error`) — never hidden
chain-of-thought. Atlas plans each turn (direct answer vs. one of four tools) and
only recalls selective, relevant conversation context. Traces are persisted for
every turn, so a call that fails mid-generation still leaves a `trace_completed`
event with a `failed` status and a safe error message.