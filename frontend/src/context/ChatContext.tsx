import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { streamChat } from "../lib/api";
import { getConversation, getTraces, listConversations } from "../lib/client";
import type {
  ChatChunkBrief,
  Citation,
  Conversation,
  SSEEvent,
  Trace,
} from "../lib/types";
import { useApp } from "./AppContext";

export interface StampedSseEvent {
  id: string;
  kind: string;
  title: string;
  description: string;
  status: "completed" | "error" | "active";
  timestamp: number;
  latencyMs?: number;
}

export interface ChatMessage {
  key: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
  citations: Citation[];
  sources: ChatChunkBrief[];
  traceId: string | null;
  trace: Trace | null;
  streaming: boolean;
  failed: boolean;
  rejected: boolean;
  groundingStatus: "passed" | "rejected" | null;
  events: StampedSseEvent[];
}

interface ChatContextValue {
  messages: ChatMessage[];
  isStreaming: boolean;
  conversations: Conversation[];
  conversationId: string | null;
  traceOpen: boolean;
  traceMessageKey: string | null;
  setTraceOpen: (open: boolean) => void;
  setTraceMessageKey: (key: string | null) => void;
  sendMessage: (text: string) => Promise<void>;
  stopStreaming: () => void;
  startNewConversation: () => Promise<void>;
  switchConversation: (id: string) => Promise<void>;
  refreshConversations: () => Promise<void>;
  clearMessages: () => void;
}

const ChatContext = createContext<ChatContextValue | null>(null);

function createMessage(partials: Partial<ChatMessage>): ChatMessage {
  return {
    key: crypto.randomUUID(),
    role: "assistant",
    content: "",
    created_at: new Date().toISOString(),
    citations: [],
    sources: [],
    traceId: null,
    trace: null,
    streaming: false,
    failed: false,
    rejected: false,
    groundingStatus: null,
    events: [],
    ...partials,
  };
}

const TOOL_LABELS: Record<string, string> = {
  search_knowledge_base: "Search knowledge base",
  retrieve_document: "Retrieve document",
  compare_documents: "Compare documents",
  get_conversation_context: "Recall conversation context",
};

export function ChatProvider({ children }: { children: ReactNode }) {
  const { knowledgeBase } = useApp();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [traceOpen, setTraceOpen] = useState(false);
  const [traceMessageKey, setTraceMessageKey] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const knowledgeBaseRef = useRef(knowledgeBase);
  knowledgeBaseRef.current = knowledgeBase;

  const refreshConversations = useCallback(async () => {
    try {
      setConversations(await listConversations(knowledgeBaseRef.current));
    } catch {
      setConversations([]);
    }
  }, []);

  useEffect(() => {
    void refreshConversations();
    setMessages([]);
    setConversationId(null);
    setTraceMessageKey(null);
  }, [knowledgeBase, refreshConversations]);

  const stopStreaming = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  const clearMessages = useCallback(() => {
    setMessages([]);
    setConversationId(null);
    setTraceMessageKey(null);
  }, []);

  const loadConversationMessages = useCallback(async (id: string) => {
    const detail = await getConversation(knowledgeBaseRef.current, id);
    const history: ChatMessage[] = detail.messages.map((message) =>
      createMessage({
        role: message.role,
        content: message.content,
        created_at: message.created_at,
      }),
    );
    setMessages(history);
    // Associate persisted traces by turn order (one trace per stored turn).
    try {
      const traceList = await getTraces(knowledgeBaseRef.current, id);
      const traceIds = traceList.traces.filter((t) => t.question);
      const assistantKeys = history.filter((m) => m.role === "assistant").map((m) => m.key);
      setMessages((current) =>
        current.map((message) => {
          const index = assistantKeys.indexOf(message.key);
          if (index >= 0 && traceIds[index]) {
            return {
              ...message,
              traceId: traceIds[index].trace_id,
              trace: traceIds[index],
            };
          }
          return message;
        }),
      );
    } catch {
      // traces may not exist for this conversation (e.g. never persisted)
    }
  }, []);

  const switchConversation = useCallback(
    async (id: string) => {
      await loadConversationMessages(id);
      setConversationId(id);
      setTraceMessageKey(null);
    },
    [loadConversationMessages],
  );

  const startNewConversation = useCallback(async () => {
    setMessages([]);
    setConversationId(null);
    setTraceMessageKey(null);
    await refreshConversations();
  }, [refreshConversations]);

  const sendMessage = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || messages.some((m) => m.streaming)) return;

      const userMessage = createMessage({ role: "user", content: trimmed });
      const assistantMessage = createMessage({ streaming: true });
      setMessages((previous) => [...previous, userMessage, assistantMessage]);

      const controller = new AbortController();
      abortRef.current = controller;
      const liveEvents: StampedSseEvent[] = [];
      let localConversationId = conversationId;
      let localTraceId: string | null = null;

      const patch = (updater: (message: ChatMessage) => ChatMessage) => {
        setMessages((previous) =>
          previous.map((message) =>
            message.key === assistantMessage.key ? updater(message) : message,
          ),
        );
      };

      const pushEvent = (event: Omit<StampedSseEvent, "id" | "timestamp">) => {
        const stamped: StampedSseEvent = {
          ...event,
          id: crypto.randomUUID(),
          timestamp: Date.now(),
        };
        liveEvents.push(stamped);
        patch((message) => ({ ...message, events: [...message.events, stamped] }));
      };

      try {
        await streamChat(
          {
            message: trimmed,
            knowledge_base_id: knowledgeBaseRef.current,
            conversation_id: localConversationId,
          },
          (sse: SSEEvent) => {
            const data = sse.data;
            switch (sse.type) {
              case "conversation":
                localConversationId = data.conversation_id as string;
                setConversationId(localConversationId);
                break;
              case "trace":
                localTraceId = data.trace_id as string;
                patch((message) => ({ ...message, traceId: localTraceId }));
                break;
              case "decision":
                if (data.source === "tool") {
                  pushEvent({
                    kind: "decision",
                    title: "Planner: tool selected",
                    description: TOOL_LABELS[(data.tool as string) ?? ""] ?? "Tool execution",
                    status: "completed",
                  });
                } else {
                  pushEvent({
                    kind: "decision",
                    title: "Planner: direct answer",
                    description: "No retrieval — answering from model knowledge.",
                    status: "completed",
                  });
                }
                break;
              case "tool_call":
                pushEvent({
                  kind: "tool",
                  title: `Tool: ${TOOL_LABELS[(data.tool as string) ?? ""] ?? data.tool}`,
                  description: "Tool executed.",
                  status: "completed",
                });
                break;
              case "retrieval":
                pushEvent({
                  kind: "retrieval",
                  title: "Retrieved relevant chunks",
                  description: `Found ${data.count as number} relevant chunks.`,
                  status: "completed",
                });
                patch((message) => ({ ...message, sources: data.chunks as ChatChunkBrief[] }));
                break;
              case "reranking":
                pushEvent({
                  kind: "rerank",
                  title: "Re-ranked results (BM25)",
                  description: `${(data.input_count as number) ?? "?"} → ${(data.output_count as number) ?? "?"} chunks via BM25.`,
                  status: "completed",
                  latencyMs: data.latency_ms as number,
                });
                break;
              case "grounding":
                pushEvent({
                  kind: "grounding",
                  title:
                    data.status === "passed"
                      ? "Grounding check passed"
                      : "Grounding check rejected",
                  description:
                    data.status === "passed"
                      ? `Best score ${(data.score as number) ?? "-"} passes threshold ${(data.threshold as number) ?? "-"}.`
                      : `No evidence reached the ${(data.threshold as number) ?? "-"} threshold.`,
                  status: data.status === "rejected" ? "error" : "completed",
                });
                patch((message) => ({
                  ...message,
                  groundingStatus: data.status as "passed" | "rejected",
                }));
                break;
              case "citation":
                pushEvent({
                  kind: "citation",
                  title: "Citations verified",
                  description: `${(data.count as number) ?? 0} source(s) matched retrieved evidence.`,
                  status: "completed",
                });
                break;
              case "status":
                if (data.stage === "generating") {
                  pushEvent({
                    kind: "generation",
                    title: "Generating response",
                    description: "Streaming tokens from the LLM.",
                    status: "completed",
                  });
                }
                break;
              case "token": {
                const text = data.text as string;
                if (liveEvents.length === 0 || liveEvents[liveEvents.length - 1].kind !== "stream") {
                  pushEvent({
                    kind: "stream",
                    title: "Response streamed",
                    description: "1 token",
                    status: "active",
                  });
                }
                patch((message) => ({ ...message, content: message.content + text }));
                break;
              }
              case "answer": {
                const text = data.text as string;
                patch((message) => ({
                  ...message,
                  content: text,
                  rejected: text.includes("No relevant information"),
                  streaming: false,
                }));
                break;
              }
              case "done": {
                const citations = data.citations as Citation[];
                patch((message) => {
                  const last = message.events[message.events.length - 1];
                  const updated = [...message.events];
                  if (last && last.kind === "stream") {
                    updated[updated.length - 1] = {
                      ...last,
                      status: "completed",
                      description: `${message.content.length} chars streamed`,
                    };
                  }
                  return {
                    ...message,
                    citations,
                    streaming: false,
                    events: updated,
                  };
                });
                break;
              }
              case "trace_completed":
                pushEvent({
                  kind: "trace_completed",
                  title: "Turn completed",
                  description:
                    data.status === "failed" ? "Turn failed — trace persisted." : "Trace persisted.",
                  status: data.status === "failed" ? "error" : "completed",
                  latencyMs: typeof data.latency_ms === "number" ? data.latency_ms : undefined,
                });
                break;
              case "error":
                pushEvent({
                  kind: "error",
                  title: "Error",
                  description: (data.message as string) ?? "Something went wrong.",
                  status: "error",
                });
                break;
              default:
                break;
            }
          },
          controller.signal,
        );
      } catch (error) {
        const aborted =
          controller.signal.aborted || (error instanceof DOMException && error.name === "AbortError");
        if (!aborted) {
          const message =
            error instanceof Error ? error.message : "The request failed unexpectedly.";
          patch((current) => ({
            ...current,
            content: current.content || message,
            failed: true,
            streaming: false,
          }));
          pushEvent({
            kind: "error",
            title: "Request failed",
            description: message,
            status: "error",
          });
        } else {
          patch((current) => ({ ...current, streaming: false }));
        }
      } finally {
        patch((current) => ({ ...current, streaming: false }));
        abortRef.current = null;
        void refreshConversations();
        if (localConversationId) {
          const traceId = localTraceId;
          try {
            const traceList = await getTraces(knowledgeBaseRef.current, localConversationId);
            const matched = traceId
              ? traceList.traces.find((t) => t.trace_id === traceId)
              : traceList.traces[traceList.traces.length - 1];
            if (matched) {
              setMessages((previous) =>
                previous.map((message) =>
                  message.key === assistantMessage.key
                    ? { ...message, traceId: matched.trace_id, trace: matched }
                    : message,
                ),
              );
            }
          } catch {
            // trace may not be retrievable for a failed turn — acceptable
          }
        }
      }
    },
    [conversationId, messages, refreshConversations],
  );

  const value = useMemo<ChatContextValue>(
    () => ({
      messages,
      isStreaming: messages.some((m) => m.streaming),
      conversations,
      conversationId,
      traceOpen,
      traceMessageKey,
      setTraceOpen,
      setTraceMessageKey,
      sendMessage,
      stopStreaming,
      startNewConversation,
      switchConversation,
      refreshConversations,
      clearMessages,
    }),
    [messages, conversations, conversationId, traceOpen, traceMessageKey, sendMessage, stopStreaming, startNewConversation, switchConversation, refreshConversations, clearMessages],
  );

  return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>;
}

export function useChat(): ChatContextValue {
  const value = useContext(ChatContext);
  if (!value) throw new Error("useChat must be used within ChatProvider");
  return value;
}