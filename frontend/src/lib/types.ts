export type DocumentStatus = "ingesting" | "indexed" | "failed";

export interface Document {
  id: string;
  knowledge_base_id: string;
  name: string;
  size: number;
  status: DocumentStatus;
  chunk_count: number;
  error: string | null;
  created_at: string;
}

export interface KnowledgeBase {
  id: string;
  document_count: number;
  chunk_count: number;
  created_at: string | null;
}

export interface DocumentChunk {
  knowledge_base_id: string;
  document_id: string;
  document_name: string;
  chunk_id: string;
  text: string;
  page: number | null;
  section: string | null;
}

export interface Health {
  status: "ok" | "degraded";
  llm_available: boolean;
  embedding_available: boolean;
}

export interface Conversation {
  id: string;
  knowledge_base_id: string;
  created_at: string;
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
}

export interface ConversationDetail extends Conversation {
  messages: Message[];
}

export interface ChatChunkBrief {
  document_id: string;
  document_name: string;
  page: number | null;
  section: string | null;
  score: number;
}

export interface Citation {
  chunk_id: string;
  document_id: string;
  document_name: string;
  page?: number | null;
  section?: string | null;
}

export interface TraceEventOut {
  event_id: string;
  trace_id: string;
  event_type: string;
  status: string;
  timestamp: string;
  conversation_id?: string | null;
  knowledge_base_id: string;
  latency_ms?: number | null;
  metadata: Record<string, unknown>;
  error?: { component: string; code: string; message: string } | null;
}

export interface Trace {
  trace_id: string;
  conversation_id?: string | null;
  knowledge_base_id: string;
  question?: string | null;
  status: string;
  started_at: string;
  completed_at?: string | null;
  latency_ms?: number | null;
  events: TraceEventOut[];
}

export interface TraceList {
  conversation_id: string;
  knowledge_base_id: string;
  traces: Trace[];
}

// ── SSE event payloads (mirror of backend/app/agent/agent.py emits) ──────────

export interface DecisionEvent {
  source: "tool" | "direct";
  tool: string | null;
  arguments: Record<string, unknown>;
}

export interface RetrievalEvent {
  count: number;
  chunks: ChatChunkBrief[];
}

export interface RerankingEvent {
  method: string;
  input_count: number;
  output_count: number;
  latency_ms: number;
}

export interface GroundingEvent {
  status: "passed" | "rejected";
  rule: string;
  score: number | null;
  threshold: number | null;
  evidence_count: number;
}

export interface CitationEvent {
  status: string;
  count: number;
  citations: Citation[];
}

export interface TokensDoneEvent {
  citations: Citation[];
}

export type SSEPayload =
  | { type: "conversation"; conversation_id: string; knowledge_base_id: string }
  | { type: "trace"; trace_id: string; conversation_id: string; knowledge_base_id: string }
  | { type: "decision" } & DecisionEvent
  | { type: "tool_call"; tool: string; arguments: Record<string, unknown> }
  | ({ type: "retrieval" } & RetrievalEvent)
  | { type: "reranking" } & RerankingEvent
  | { type: "tool_summary"; tool: string; summary: string }
  | ({ type: "grounding" } & GroundingEvent)
  | ({ type: "citation" } & CitationEvent)
  | { type: "status"; stage: string }
  | { type: "token"; text: string }
  | ({ type: "done" } & TokensDoneEvent)
  | { type: "answer"; text: string }
  | { type: "memory"; count: number; messages: { role: string; content: string }[] }
  | { type: "trace_completed"; trace_id: string; conversation_id: string; status: string; latency_ms: number | null }
  | { type: "error"; message: string };

export interface SSEEvent {
  type: string;
  data: Record<string, unknown>;
}

export type ChatEventCallback = (event: SSEEvent) => void;