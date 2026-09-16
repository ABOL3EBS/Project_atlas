import type { ChatChunkBrief, TraceEventOut } from "./types";
import type { ChatMessage, StampedSseEvent } from "../context/ChatContext";

export interface TraceRow {
  id: string;
  kind:
    | "default"
    | "decision"
    | "tool"
    | "retrieval"
    | "rerank"
    | "grounding"
    | "citation"
    | "generation"
    | "stream"
    | "done"
    | "trace_completed"
    | "error";
  title: string;
  description: string;
  status: "completed" | "error" | "active";
  timestamp: number;
  latencyMs?: number | null;
}

export interface TraceSource {
  documentId: string;
  documentName: string;
  page?: number | null;
  section?: string | null;
}

export interface TraceView {
  rows: TraceRow[];
  sources: TraceSource[];
  performance: {
    totalMs: number | null;
    retrievalMs: number | null;
    generationMs: number | null;
  };
  rejected: boolean;
}

const EVENT_TITLES: Record<string, { title: string; completion: string }> = {
  trace_started: { title: "Trace started", completion: "Turn recorded." },
  agent_started: { title: "Turn started", completion: "Agent run began." },
  decision: { title: "Planner decision", completion: "Tool selected." },
  tool_call: { title: "Tool execution", completion: "Tool completed." },
  retrieval: { title: "Retrieved chunks", completion: "Chunks retrieved from vector store." },
  reranking: { title: "Re-ranked results (BM25)", completion: "BM25 rerank finished." },
  grounding: { title: "Grounding check", completion: "Grounding evaluated." },
  citation: { title: "Citation verified", completion: "Citation matched retrieved evidence." },
  generation_started: { title: "Generation started", completion: "Response begun." },
  generation_completed: { title: "Generation finished", completion: "Response streamed." },
  trace_completed: { title: "Turn completed", completion: "Trace persisted." },
  error: { title: "Error", completion: "Turn failed." },
};

function describePersistedEvent(event: TraceEventOut): string {
  const metadata = event.metadata ?? {};
  switch (event.event_type) {
    case "decision":
      return metadata.source === "direct"
        ? "Answered from model knowledge, no retrieval."
        : `Planned tool: ${String(metadata.tool ?? "unknown")}.`;
    case "retrieval":
      return `${String(metadata.returned ?? "?")} of ${String(metadata.candidates ?? "?")} candidate chunk(s) retrieved.`;
    case "reranking":
      return `BM25 ${String(metadata.input_count ?? "?")} → ${String(metadata.output_count ?? "?")} chunk(s).`;
    case "grounding":
      if (event.status === "rejected") {
        return `Rejected — no evidence reached threshold ${String(metadata.threshold ?? "-")}.`;
      }
      return `Passed — best score ${String(metadata.score ?? "-")} ≥ threshold ${String(metadata.threshold ?? "-")}.`;
    case "citation":
      return `${String(metadata.document_name ?? "document")} · page ${String(metadata.page ?? "-")}${metadata.section ? ` · ${metadata.section}` : ""}.`;
    case "generation_completed":
      return "Response fully streamed.";
    case "tool_call":
      return `Tool ${String(metadata.tool ?? "unknown")} executed.`;
    default:
      return EVENT_TITLES[event.event_type]?.completion ?? "Event recorded.";
  }
}

function kindForEventType(eventType: string): TraceRow["kind"] {
  switch (eventType) {
    case "decision":
      return "decision";
    case "tool_call":
      return "tool";
    case "retrieval":
      return "retrieval";
    case "reranking":
      return "rerank";
    case "grounding":
      return "grounding";
    case "citation":
      return "citation";
    case "generation_started":
    case "generation_completed":
      return "generation";
    case "trace_completed":
      return "trace_completed";
    case "error":
      return "error";
    default:
      return "default";
  }
}

function persistedRows(trace: { events: TraceEventOut[] }): TraceRow[] {
  return trace.events.map((event) => {
    const meta = EVENT_TITLES[event.event_type];
    let status: "completed" | "error" | "active" = "completed";
    if (event.event_type === "error" || event.status === "error" || event.status === "rejected") {
      status = "error";
    } else if (event.status === "active") {
      status = "active";
    }
    return {
      id: event.event_id,
      kind: kindForEventType(event.event_type),
      title: meta?.title ?? event.event_type.replaceAll("_", " "),
      description: describePersistedEvent(event),
      status,
      timestamp: new Date(event.timestamp).getTime(),
      latencyMs: event.latency_ms,
    };
  });
}

function liveRows(events: StampedSseEvent[]): TraceRow[] {
  return events.map((event) => ({
    id: event.id,
    kind: event.kind as TraceRow["kind"],
    title: event.title,
    description: event.description,
    status: event.status,
    timestamp: event.timestamp,
    latencyMs: event.latencyMs,
  }));
}

function sourcesFromCitations(trace: { events: TraceEventOut[] }): TraceSource[] {
  const seen = new Set<string>();
  const sources: TraceSource[] = [];
  for (const event of trace.events) {
    if (event.event_type !== "citation") continue;
    const metadata = event.metadata ?? {};
    const key = String(metadata.chunk_id ?? `${metadata.document_id}-${metadata.page}`);
    if (seen.has(key)) continue;
    seen.add(key);
    sources.push({
      documentId: String(metadata.document_id ?? ""),
      documentName: String(metadata.document_name ?? "Unknown document"),
      page: typeof metadata.page === "number" ? metadata.page : null,
      section: metadata.section ? String(metadata.section) : null,
    });
  }
  return sources;
}

function latencyFor(
  trace: { events: TraceEventOut[]; latency_ms?: number | null },
  type: string,
): number | null {
  const event = trace.events.find((item) => item.event_type === type);
  return typeof event?.latency_ms === "number" ? event.latency_ms : null;
}

export function buildTraceView(
  message: ChatMessage,
  allTraceEvents: { events: TraceEventOut[]; latency_ms?: number | null },
): TraceView {
  if (message.trace) {
    const rejected =
      message.groundingStatus === "rejected" ||
      message.rejected ||
      allTraceEvents.events.some(
        (event) => event.event_type === "grounding" && event.status === "rejected",
      );
    return {
      rows: persistedRows(allTraceEvents),
      sources:
        message.sources.length > 0
          ? message.sources.map((chunk) => ({
              documentId: chunk.document_id,
              documentName: chunk.document_name,
              page: chunk.page,
              section: chunk.section,
            }))
          : sourcesFromCitations(allTraceEvents),
      performance: {
        totalMs: typeof allTraceEvents.latency_ms === "number" ? allTraceEvents.latency_ms : null,
        retrievalMs: latencyFor(allTraceEvents, "retrieval"),
        generationMs: latencyFor(allTraceEvents, "generation_completed"),
      },
      rejected,
    };
  }

  const live = message.events;
  const traceCompleted = live.find(
    (event) => event.kind === "trace_completed" && typeof event.latencyMs === "number",
  );
  const totalMs =
    typeof traceCompleted?.latencyMs === "number" ? traceCompleted.latencyMs : null;
  return {
    rows: liveRows(live),
    sources: chunkBriefsToSources(message.sources),
    performance: {
      totalMs,
      retrievalMs: null,
      generationMs: null,
    },
    rejected: message.groundingStatus === "rejected" || message.rejected,
  };
}

export function chunkBriefsToSources(chunks: ChatChunkBrief[]): TraceSource[] {
  return chunks.map((chunk) => ({
    documentId: chunk.document_id,
    documentName: chunk.document_name,
    page: chunk.page,
    section: chunk.section,
  }));
}