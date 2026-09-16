# Atlas — Agentic Knowledge Assistant

## 1. Project Overview

**Atlas** is a portfolio-grade, production-oriented AI knowledge and research agent.

The goal is NOT to build another generic "chat with PDFs" application. Atlas should demonstrate real AI engineering concepts:

> Document ingestion → chunking → embeddings → vector retrieval → agentic tool selection → reranking → grounded generation → citations → observable execution traces → evaluation

Users should be able to upload a collection of documents and interact with Atlas through a web chat interface. Atlas should answer questions using the uploaded knowledge base, retrieve evidence, cite sources, maintain conversation context, and expose a safe, useful execution trace.

The MVP should be possible to develop for **$0** using local/open-source components. The architecture should also support external LLM providers later.

---

# 2. Product Concept

### Name

**Atlas**

### Subtitle

**Agentic Knowledge Assistant**

### One-line description

> Atlas turns your documents into an evidence-backed AI research assistant.

### GitHub description

> An agentic RAG system that ingests documents, performs semantic retrieval, dynamically selects tools, maintains conversational context, and produces citation-backed answers with observable execution traces and automated evaluation.

---

# 3. What Atlas Does

A user uploads:

- PDF files
- Markdown files
- TXT files

Atlas processes them into a searchable knowledge base.

The user can then ask questions such as:

> "What are the requirements for deploying this system?"

> "Can this be deployed on-premise?"

> "What's the difference between the Pro and Enterprise plans?"

> "I followed the installation guide but authentication isn't working. What should I check?"

Atlas should:

1. Understand the user's question.
2. Determine whether knowledge-base retrieval is necessary.
3. Generate or rewrite search queries when useful.
4. Search the vector database.
5. Retrieve relevant chunks.
6. Optionally retrieve additional context or search multiple queries.
7. Re-rank retrieved results where appropriate.
8. Generate a grounded answer.
9. Cite the source documents and page/section information when available.
10. Maintain conversational context.
11. Show an execution trace containing observable actions.

---

# 4. Important Product Principle

Atlas is an **agent**, not merely:

```text
question
    ↓
embedding
    ↓
similarity search
    ↓
LLM
```

The agent should have access to tools and should decide when those tools are useful.

Example tools:

```python
search_knowledge_base()
retrieve_document()
compare_documents()
get_conversation_context()
```

The agent can choose between:

```text
Direct answer
    OR
Knowledge-base search
    OR
Multiple searches
    OR
Document comparison
```

Do NOT implement fake agent behavior just to make the project look agentic. Tool selection should have a real purpose.

---

# 5. Example Interaction

User uploads:

```text
knowledge/
├── installation.pdf
├── API_reference.pdf
├── troubleshooting.md
├── security.pdf
└── pricing.md
```

User asks:

> "Can I deploy this on-premise, and what are the minimum requirements?"

Atlas might execute:

```text
Agent Trace

✓ Classified question
  → Documentation lookup

✓ Generated retrieval queries
  → "on-premise deployment"
  → "minimum infrastructure requirements"

✓ Retrieved 12 chunks

✓ Re-ranked results
  → 5 highly relevant chunks

✓ Generated grounded response

✓ Verified citations
```

Response:

```text
Yes. The documentation supports on-premise deployment.

The minimum production configuration requires ...

Sources:
- installation.pdf — page 18
- security.pdf — page 7
```

The exact content must always come from the uploaded knowledge base.

---

# 6. Architecture

Use a clean modular architecture:

```text
                         ┌─────────────────────┐
                         │      Web Client     │
                         │    React / Next.js  │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │      FastAPI        │
                         │        API          │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │      Atlas Agent    │
                         │                     │
                         │ Query understanding │
                         │ Tool selection      │
                         │ Context management  │
                         │ Response generation │
                         └──────┬───────┬──────┘
                                │       │
                 ┌──────────────┘       └──────────────┐
                 ▼                                     ▼
        ┌─────────────────┐                   ┌─────────────────┐
        │ Retrieval Layer │                   │   LLM Layer     │
        │                 │                   │                 │
        │ Vector search   │                   │ Local / API     │
        │ Filtering       │                   │ generation      │
        │ Reranking       │                   │ tool decisions  │
        └────────┬────────┘                   └─────────────────┘
                 ▲
                 │
        ┌────────┴────────┐
        │ Ingestion Layer │
        │                 │
        │ PDF parsing     │
        │ Text extraction │
        │ Chunking        │
        │ Embeddings      │
        └─────────────────┘
```

---

# 7. Recommended Technology Direction

Keep the technology practical and understandable.

## Backend

- Python
- FastAPI
- Pydantic
- Async where useful

## Frontend

Prefer:

- React
- TypeScript
- Tailwind CSS

A simple clean chat UI is enough. Do not spend most of the project building visual effects.

## Document Processing

Start with:

- PyMuPDF for PDF extraction
- Markdown parser / plain text handling

Design ingestion so additional formats can be added later.

## Embeddings

Use a local Sentence Transformers model.

The embeddings must run locally so the MVP can be completely free.

Create an abstraction:

```python
class EmbeddingProvider:
    def embed_documents(...)
    def embed_query(...)
```

Do not hard-code the entire system around one model.

## Vector Store

For the MVP use one simple local vector database.

Possible choices:

- ChromaDB
- FAISS
- Qdrant

Prefer the option that keeps the implementation simple and reproducible.

The vector layer should be behind an interface so it can be replaced later.

## LLM

Support a local LLM through Ollama for a $0 development path.

Create an abstraction:

```python
class LLMProvider:
    def generate(...)
    def stream(...)
```

Implement the local provider first.

Design the architecture so OpenAI/Anthropic/etc. can be added later without rewriting the agent.

---

# 8. $0 Requirement

The project should be completely usable locally without paid APIs.

Target local architecture:

```text
React
   ↓
FastAPI
   ↓
Atlas Agent
   ├── Ollama
   ├── Sentence Transformers
   ├── ChromaDB/FAISS/Qdrant
   └── SQLite
```

Everything should run on the developer's machine.

Do NOT require an OpenAI API key for the basic demo.

External providers can be optional.

---

# 9. LLM Provider Abstraction

Do not couple the agent directly to Ollama.

Use something like:

```text
LLMProvider
├── OllamaProvider
├── OpenAIProvider
└── AnthropicProvider (future)
```

The agent should interact with the interface rather than a specific vendor.

This demonstrates good software architecture and makes the project easier to deploy.

---

# 10. Embedding / Retrieval Pipeline

Implement the complete pipeline.

```text
Document
   ↓
Text extraction
   ↓
Cleaning
   ↓
Chunking
   ↓
Metadata attachment
   ↓
Embedding
   ↓
Vector storage
```

Each chunk should preserve useful metadata:

```json
{
  "document_id": "...",
  "document_name": "installation.pdf",
  "chunk_id": "...",
  "page": 18,
  "section": "Deployment",
  "text": "..."
}
```

The exact metadata depends on the source format.

---

# 11. Chunking

Do not blindly split text.

Create a configurable chunking component.

Initial approach:

- Target chunk size around 500 tokens
- Overlap around 50 tokens
- Preserve document/page/section metadata
- Avoid splitting in the middle of obvious structural units when possible

The configuration should be easy to change for experiments.

Example:

```python
ChunkingConfig(
    chunk_size=500,
    chunk_overlap=50
)
```

Do not treat these numbers as universally optimal. They are initial defaults that should be evaluated.

---

# 12. Retrieval

Start with semantic vector search.

Then add optional improvements:

### Stage 1

```text
query
 ↓
embedding
 ↓
vector search
 ↓
top K chunks
```

### Stage 2

```text
query
 ↓
query expansion / rewriting
 ↓
multiple searches
 ↓
candidate chunks
 ↓
deduplication
 ↓
reranking
 ↓
final context
```

Do not over-engineer the first version.

Build the simple pipeline first, then measure whether improvements actually help.

---

# 13. Agent Tools

The first version should have a small number of meaningful tools.

## `search_knowledge_base`

Purpose:

Search the uploaded knowledge base for relevant information.

Input:

```text
query
top_k
optional filters
```

Output:

```text
retrieved chunks
metadata
similarity/relevance information
```

---

## `retrieve_document`

Purpose:

Retrieve more context from a specific document when the initial chunks are insufficient.

Useful when the agent needs broader context.

---

## `compare_documents`

Purpose:

Compare information across documents.

Example:

> "Compare the deployment requirements in the enterprise and standard documentation."

This demonstrates multi-document reasoning.

---

## `get_conversation_context`

Purpose:

Retrieve relevant previous conversation information.

Do not automatically dump the entire chat history into every prompt.

---

# 14. Agent Decision Flow

The agent should conceptually follow:

```text
User question
      ↓
Understand intent
      ↓
Does this require the knowledge base?
      │
   ┌──┴──┐
   │     │
  No    Yes
   │     │
Answer   Determine search strategy
         ↓
      Search KB
         ↓
   Are results sufficient?
      │
   ┌──┴──┐
   │     │
  Yes    No
   │     │
Answer  Additional search /
        document retrieval
            ↓
          Answer
            ↓
      Add citations
            ↓
       Return result
```

The system should refuse to invent information that is not supported by the knowledge base when the user is asking about the uploaded material.

For unsupported questions, say clearly that the information was not found.

---

# 15. Citations

Citations are a core feature.

Every knowledge-grounded answer should identify its evidence.

Example:

```text
Atlas:

The system supports on-premise deployment. The documented
minimum requirements include ...

Sources:
[1] installation.pdf — page 18
[2] security.pdf — page 7
```

Ideally, clicking a citation in the UI should show the relevant chunk.

Citation metadata must come from the actual document.

Never fabricate page numbers or sources.

---

# 16. Conversation Memory

Atlas should maintain short-term conversational context.

Example:

```text
User:
What authentication methods are supported?

Atlas:
OAuth and API keys.

User:
Which one should I use for server-to-server applications?

Atlas:
For server-to-server applications, the documentation recommends ...
```

The system should understand references such as:

- "it"
- "that"
- "the first one"
- "what about Enterprise?"
- "compare that with the previous document"

Keep memory implementation simple for the MVP.

SQLite can store conversations and messages.

---

# 17. Agent Trace

This is an important portfolio feature.

Expose **observable execution events**, not private chain-of-thought.

Example:

```text
Agent Trace

08:42:11  Query classified
08:42:11  Retrieval required
08:42:11  Search query generated
08:42:12  Vector search completed
08:42:12  10 chunks retrieved
08:42:12  Results re-ranked
08:42:13  Context assembled
08:42:14  Response generated
08:42:14  Citations attached
```

The trace may expose:

- tool calls
- search queries
- number of retrieved chunks
- selected documents
- latency
- token usage if available
- errors
- final citation references

Do NOT expose hidden chain-of-thought or internal reasoning.

---

# 18. Evaluation System

This is required for the portfolio version.

Create a small evaluation dataset.

Example:

```json
{
  "question": "How do I configure OAuth?",
  "expected_sources": [
    "authentication.md"
  ]
}
```

Target 20–50 test questions initially.

Measure:

- Retrieval Recall@K
- MRR
- Citation accuracy
- Answer relevance
- Faithfulness / groundedness
- Latency
- Token usage where available

Example output:

```text
Atlas Evaluation

Retrieval Recall@5     94%
MRR                     0.89
Citation Accuracy      96%
Faithfulness            93%
Average Latency         1.8s
```

These numbers are examples only. Never put fabricated metrics in the README. Generate real numbers from the evaluation system.

---

# 19. Evaluation Philosophy

Do not optimize blindly.

The project should allow experiments such as:

```text
Experiment A
chunk_size = 500
overlap = 50

Experiment B
chunk_size = 800
overlap = 100
```

Then compare retrieval and answer quality.

Similarly test:

- top_k
- embedding models
- reranking
- query expansion
- prompt changes

The README should eventually contain real evaluation results.

---

# 20. User Interface

Keep the UI clean and professional.

Main screens:

## Knowledge Base

```text
Atlas

Knowledge Base
────────────────────────────

Upload documents

[ Drop files here ]

Documents
✓ installation.pdf
✓ security.pdf
✓ troubleshooting.md
```

## Chat

```text
Atlas

────────────────────────────────

User:
Can this be deployed on-premise?

Atlas:
Yes. According to the documentation...

Sources:
[installation.pdf · p.18]
[security.pdf · p.7]

────────────────────────────────

Ask Atlas...
```

## Trace

Optional expandable panel:

```text
Execution Trace

✓ Query classification
✓ Knowledge search
✓ 12 chunks retrieved
✓ Reranking
✓ Response generation
✓ Citation verification
```

Do not let UI complexity distract from the AI engineering.

---

# 21. API Direction

Potential endpoints:

```text
POST   /api/documents/upload
GET    /api/documents
DELETE /api/documents/{id}

POST   /api/chat
GET    /api/conversations
GET    /api/conversations/{id}

GET    /api/trace/{conversation_id}

POST   /api/evaluation/run
GET    /api/evaluation/results

GET    /api/health
```

Use streaming responses for chat if practical.

Server-Sent Events are a reasonable option.

---

# 22. Docker

The application should eventually run through Docker.

Target:

```bash
docker compose up
```

and then the user can access Atlas locally.

The README should explain:

```text
1. Clone repository
2. Copy .env.example to .env
3. Start Ollama/model
4. docker compose up
5. Open the web interface
```

Do not make the setup unnecessarily complicated.

---

# 23. Hosting

The application should be designed so it can eventually be hosted publicly.

Important distinction:

### Development

Everything can run locally for $0.

### Public demo

A lightweight hosted frontend/backend can be deployed using available free tiers, subject to current provider limits.

Do not architect the application around a paid service.

The system should support:

```text
Local LLM
OR
External LLM API
```

A public demo can use a configurable provider.

If hosting a shared instance, protect it with basic limits/rate limiting and do not allow users to consume unlimited expensive resources.

---

# 24. Security / Privacy Basics

Since users upload documents:

- Validate file types.
- Limit upload size.
- Sanitize filenames.
- Do not execute uploaded files.
- Isolate uploaded content from application code.
- Never put secrets into uploaded documents intentionally.
- Do not log full document contents unnecessarily.
- Do not expose another user's knowledge base.
- Scope documents and conversations to the correct user/session.
- Add basic rate limiting for public deployments.

For the MVP, authentication can be simple or omitted locally, but the architecture should make data isolation possible.

---

# 25. Suggested Repository Structure

```text
atlas/
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── agent/
│   │   ├── ingestion/
│   │   ├── retrieval/
│   │   ├── embeddings/
│   │   ├── llm/
│   │   ├── memory/
│   │   ├── models/
│   │   ├── services/
│   │   └── main.py
│   │
│   └── tests/
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── hooks/
│   │   └── lib/
│   └── package.json
│
├── evaluation/
│   ├── datasets/
│   ├── runners/
│   └── results/
│
├── knowledge/
│   └── example/
│
├── docker-compose.yml
├── Dockerfile
├── .env.example
├── README.md
└── LICENSE
```

The exact structure can change if there is a better engineering reason.

---

# 26. Development Milestones

## Milestone 1 — Basic RAG

Goal:

```text
Upload PDF
 ↓
Extract text
 ↓
Chunk
 ↓
Embed
 ↓
Store
 ↓
Search
 ↓
LLM answer
```

No fancy agent yet.

---

## Milestone 2 — Citations

Add:

- document metadata
- page numbers
- source references
- citations in responses

---

## Milestone 3 — Agent

Add:

- tool definitions
- tool selection
- search tool
- document retrieval tool
- conversation context

---

## Milestone 4 — Better Retrieval

Add:

- query rewriting
- multi-query retrieval
- deduplication
- reranking

Only keep improvements that demonstrate measurable benefit.

---

## Milestone 5 — Agent Trace

Add observable execution events.

---

## Milestone 6 — Evaluation

Build the benchmark dataset and automated metrics.

---

## Milestone 7 — UI Polish

Build a clean React interface.

---

## Milestone 8 — Docker / Deployment

Make the system reproducible and deployable.

---

# 27. What NOT To Do

Do not turn this into:

- a generic ChatGPT clone
- a simple LangChain tutorial
- "upload PDF → ask question" with no engineering depth
- an overcomplicated multi-agent system
- a fake agent where every request follows the exact same pipeline
- a UI-first project with little backend engineering
- a project full of placeholder implementations
- an application requiring paid APIs just to run locally

Avoid adding five agents simply because "multi-agent" sounds impressive.

One well-designed agent with meaningful tools is enough.

---

# 28. Portfolio Goal

The finished project should demonstrate that the developer understands:

### AI Engineering

- embeddings
- vector search
- RAG
- chunking
- retrieval
- reranking
- grounding
- citations
- LLM tool calling
- agent architecture
- conversation memory
- evaluation

### Software Engineering

- Python
- FastAPI
- TypeScript/React
- modular architecture
- interfaces/abstractions
- testing
- Docker
- API design
- async/streaming
- error handling

### Production Thinking

- observability
- latency
- evaluation
- privacy
- rate limiting
- provider abstraction
- reproducibility

The project should make it obvious from the repository that the developer understands more than simply calling an LLM API.

---

# 29. Definition of Done

Atlas is ready for the portfolio when a new user can:

1. Open the web application.
2. Upload one or more documents.
3. Wait for ingestion to complete.
4. Ask questions about the documents.
5. Receive grounded answers.
6. See citations.
7. Continue the conversation naturally.
8. Inspect the agent's observable execution trace.
9. Run the evaluation suite locally.
10. Start the entire project using documented setup instructions.

The repository should include:

- clean README
- architecture diagram
- setup instructions
- Docker configuration
- tests
- evaluation dataset
- evaluation results generated by the actual system
- example knowledge base
- screenshots/GIF of the application
- clear explanation of design decisions

---

# 30. Final Product Positioning

Do not market Atlas as:

> "An AI chatbot."

Market it as:

> **Atlas — Agentic Knowledge Assistant**

> An open-source AI agent that turns unstructured documents into an evidence-backed research assistant. Atlas combines document ingestion, semantic retrieval, agentic tool selection, reranking, conversational memory, citation-backed generation, execution tracing, and automated evaluation.

The strongest demonstration is:

```text
Upload
  ↓
Understand
  ↓
Retrieve
  ↓
Reason with tools
  ↓
Generate
  ↓
Cite
  ↓
Evaluate
```

Build the simplest correct version first. Measure it. Then add complexity only when it provides a measurable improvement.
