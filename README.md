# Atlas — Agentic Knowledge Assistant

## What Atlas is

Atlas turns your documents into an evidence-backed AI research assistant. You upload
PDFs, markdown, or text; Atlas chunks and embeds them into a knowledge base, and an
agentic backend plans every turn — deciding whether to answer directly or call a
retrieval tool — then grounds the answer in retrieved evidence, verifies each
citation against that evidence, and streams the result to a React frontend over SSE.
Two things make this more than a toy RAG demo: every execution step of a turn is
recorded as a structured, KB-scoped execution trace (observability as a first-class
feature, not a log dump), and the unsupported-question rejection gate is tuned from
measurement — a grounding threshold calibrated on 68 real questions — rather than a
guessed constant. The whole stack runs locally on Ollama + ChromaDB for $0, and every
retrieval and answer-quality claim in this README comes from an automated evaluation
harness writing real numbers to `evaluation/results/`, not from estimation.

Status: **M0–M7 complete**. M8 (Docker Compose deployment) is not started. See
`ATLAS_PROJECT_SPEC.md` (spec) and `IMPLEMENTATION_PLAN.md` (plan, measured results).

## Screenshot

<!-- TODO: add a real screenshot of the Chat screen — a grounded answer with clickable
citation chips, and the per-turn execution trace panel alongside the retrieved sources. -->

## Features

**Chat** — streaming answers with markdown over SSE; clickable citation chips that
open a drawer showing the exact retrieved chunk text; conversation history with
resume via `conversation_id`; knowledge-base selector; show/hide execution trace.

**Knowledge base** — upload (PDF/markdown/txt), per-document status badges, file
preview, and delete-with-confirm that removes documents and their vectors.

**Execution trace (observability)** — every real step of a turn is recorded
(`decision`, `tool_call`, `retrieval`, `reranking`, `grounding`, `citation`,
`generation_started`/`completed`), streamed live on the same SSE channel, then
persisted to SQLite (`backend/data/traces.db`) and retrievable via
`GET /api/trace/{conversation_id}` with strict knowledge-base isolation. Traces expose
telemetry only — latency, scores, counts, KB id. They never contain retrieved
document text, the user query, tool arguments, model reasoning, system prompts, or
secrets.

**Unsupported-question rejection** — a grounding gate separates questions the
knowledge base can answer from ones it cannot. Out-of-domain questions are explicitly
rejected with NOT_FOUND instead of being answered from nothing. The threshold is
calibrated on measurement (see Evaluation), currently **0.60**.

**Settings** — live `/api/health` provider status; configuration is read-only by
design because runtime settings are `.env`-driven.

## Architecture

Turn pipeline: planner (direct answer vs. one of four tools) → retrieval tool →
vector search → **BM25 reranking** → **grounding check** (calibrated threshold) →
citation verification → streamed generation. Conversation memory is selective,
recalling only relevant prior context per turn.

Stack: Python 3.12 (uv) + FastAPI backend; ChromaDB behind a `VectorStore` interface;
Ollama (`gemma2` + `nomic-embed-text`) behind swappable `LLMProvider` /
`EmbeddingProvider` interfaces; SQLite for execution traces; React + TypeScript +
Vite + Tailwind frontend (`frontend/`); Docker Compose planned for M8.

Key API surface: `POST /api/documents/upload`, `GET /api/documents`,
`GET /api/documents/knowledge-bases`, `GET /api/documents/{id}/chunks`,
`DELETE /api/documents/{id}`, `POST /api/chat` (SSE), `GET /api/conversations[/{id}]`,
`GET /api/trace/{conversation_id}`, `GET /api/health`.

Design decisions are measured, not assumed. BM25 reranking is wired into the
production `SearchKnowledgeBaseTool` because it measured **+0.024 MRR at +2 ms** on
the evaluation corpus. LLM query rewrite and multi-query expansion are not in
production because they measured worse or equal quality at 26×–43× latency. The
grounding threshold is 0.60 because that is where the measured accept/reject curves
separate, not because it looked reasonable.

## Evaluation

All numbers come from `evaluation/runners/` running against the real evaluation
dataset (`knowledge/eval/` — 12 documents, 39 chunks) with hand-labelled questions.
Evaluation artifacts are gitignored; only the datasets are checked in.

### Retrieval (48 questions)

| Pipeline | Recall@5 | MRR | Latency |
|---|---|---|---|
| Baseline embedding search | 1.0000 | 0.9653 | 17.3 ms |
| + BM25 reranking (adopted) | 1.0000 | **0.9896** | 19.3 ms |
| + LLM query rewrite (rejected) | 0.9583 | 0.8889 | 455.6 ms |
| Multi-query → dedup → rerank (rejected) | 1.0000 | 0.9896 | 753.5 ms |

BM25 reranking was adopted after the delta was measured: it fixes all three related-topic
ordering misses at +2 ms. The other two techniques were rejected on the same corpus —
rewrite degraded 8/48 questions (2 recall failures), multi-query tied reranking at 39×
latency.

### Grounding gate calibration (20 unsupported + 48 supported questions)

The gate was calibrated by running the same real search scores as an accept/reject
curve:

| Threshold | 0.45 | 0.50 | 0.55 | **0.60** | 0.65 |
|---|---|---|---|---|---|
| True accept (48 supported) | 1.0000 | 1.0000 | 1.0000 | **1.0000** | 0.7500 |
| False accept (20 unsupported) | 0.9500 | 0.7500 | 0.2500 | **0.0000** | 0.0000 |

The supported floor (≥ 0.604) and unsupported ceiling (≤ 0.587) separate cleanly at
**0.60**, so the production default moved 0.45 → 0.60. Honest caveat: "0.0000" is
**0/20 observed** — the best separator found, one grid step from the next threshold on
a 20-question sample, not a hard guarantee against a future adversarial query. After
this change the same recordings project gate false-accepts 19/20 → 0/20 with
supported acceptance unchanged (48/48).

### End-to-end answer evaluation (68 questions: 48 supported + 20 unsupported)

Measures generated answers, not just retrieval:

| Metric | Value |
|---|---|
| Unsupported rejection (E2E) | 0.20 (4/20) |
| Supported answer rate | 0.98 (47/48) |
| Citation precision | 0.60 |
| Citation coverage | 0.95 |
| Faithfulness (LLM judge, n=42) | 0.90 |
| Full-turn latency mean / median / p90 | 6326 / 6150 / 8340 ms |

Reading the two layers separately matters: the **gate** is well-calibrated at 0.60,
but **end-to-end rejection is lower** because the planner answers most unsupported
questions directly, without ever searching — so the gate is never reached for them.
The threshold change fixes the gate, not the planner; planner routing is the
documented follow-up, not something folded silently into this milestone.

## Known limitations & next steps

- **Citation precision ~0.60** — roughly 40% of cited documents don't precision-match.
  Measured and tracked, not silently fixed.
- **Planner bypasses retrieval on out-of-domain questions** — this is why E2E
  rejection (0.20) trails the gate's calibrated behavior. Planner routing is the
  follow-up.
- The faithfulness judge is the local 2b model (judge quality is itself an open item).
- "0/20 false-accepts at 0.60" is an observed sample on 20 questions, not a guarantee.
- Retrieval-side rejected options are documented (rewrite, multi-query) so a larger
  corpus can re-test them against these baselines.

## Getting started

### 1. Install dependencies

```bash
# Python 3.12 + uv (package manager)
brew install uv        # or: curl -LsSf https://astral.sh/uv/install.sh | sh

# Ollama (models run locally)
brew install ollama
brew services start ollama
ollama pull gemma2:2b
ollama pull nomic-embed-text

# Node.js (for the frontend)
brew install node     # verify with `node --version`
```

### 2. Set up the project once

```bash
cd backend && uv sync && cp .env.example .env   # backend deps + env file
cd ../frontend && npm install                    # frontend deps
```

### 3. Run — one command

From the repo root:

```bash
scripts/dev.sh start    # backend (:8000) + frontend (:5173), waits for health
scripts/dev.sh stop     # kill both
scripts/dev.sh status   # running or stopped
scripts/dev.sh restart
```

Open http://localhost:5173. Logs: `tail -f /tmp/atlas_backend.log /tmp/atlas_vite.log`.
Verify the API with `GET http://localhost:8000/api/health` (providers must report
available; that means Ollama is up with the models pulled).

Environment (`backend/.env`, from `.env.example`): `LLM_PROVIDER=ollama`,
`LLM_MODEL=gemma2:2b`, `EMBEDDING_PROVIDER=ollama`,
`EMBEDDING_MODEL=nomic-embed-text`, `OLLAMA_BASE_URL=http://localhost:11434`,
`GROUNDING_THRESHOLD=0.60`. Manual runs (instead of `dev.sh`): `uv run uvicorn
app.main:app --port 8000` in `backend/`, `npm run dev` in `frontend/` (Vite proxies
`/api` → :8000). The UI source of truth is
`frontend/src/components/agent-dashboard-spec.md`.

Reproduce the evaluation numbers:

```bash
cd backend
uv run python ../evaluation/runners/run_retrieval.py    # M4 retrieval experiments
uv run python ../evaluation/runners/run_answer_eval.py  # M6 answer evaluation
```

Results are written to `evaluation/results/` — pipeline numbers in Atlas docs always
come from these runs, never from estimation.

## Tests

`cd backend && uv run pytest` — **167 tests, all passing**; `uvx ruff check .` clean.
Frontend: `cd frontend && npm run build && npm run typecheck`.