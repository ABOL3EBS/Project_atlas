import { ApiError, parseErrorPayload } from "./api";
import type {
  Conversation,
  ConversationDetail,
  Document,
  DocumentChunk,
  Health,
  KnowledgeBase,
  TraceList,
} from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) {
    throw new ApiError(response.status, await parseErrorPayload(response));
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export function getHealth(): Promise<Health> {
  return request<Health>("/api/health");
}

export function listKnowledgeBases(): Promise<KnowledgeBase[]> {
  return request<KnowledgeBase[]>("/api/documents/knowledge-bases");
}

export function listDocuments(knowledgeBaseId: string): Promise<Document[]> {
  const params = new URLSearchParams({ knowledge_base_id: knowledgeBaseId });
  return request<Document[]>(`/api/documents?${params.toString()}`);
}

export function uploadDocument(knowledgeBaseId: string, file: File): Promise<Document> {
  const form = new FormData();
  form.append("file", file);
  form.append("knowledge_base_id", knowledgeBaseId);
  return request<Document>("/api/documents/upload", { method: "POST", body: form });
}

export function deleteDocument(knowledgeBaseId: string, documentId: string): Promise<void> {
  const params = new URLSearchParams({ knowledge_base_id: knowledgeBaseId });
  return request<void>(`/api/documents/${documentId}?${params.toString()}`, { method: "DELETE" });
}

export function getDocumentChunks(knowledgeBaseId: string, documentId: string): Promise<DocumentChunk[]> {
  const params = new URLSearchParams({ knowledge_base_id: knowledgeBaseId });
  return request<DocumentChunk[]>(`/api/documents/${documentId}/chunks?${params.toString()}`);
}

export function listConversations(knowledgeBaseId: string): Promise<Conversation[]> {
  const params = new URLSearchParams({ knowledge_base_id: knowledgeBaseId });
  return request<Conversation[]>(`/api/conversations?${params.toString()}`);
}

export function getConversation(knowledgeBaseId: string, conversationId: string): Promise<ConversationDetail> {
  const params = new URLSearchParams({ knowledge_base_id: knowledgeBaseId });
  return request<ConversationDetail>(`/api/conversations/${conversationId}?${params.toString()}`);
}

export function getTraces(knowledgeBaseId: string, conversationId: string): Promise<TraceList> {
  const params = new URLSearchParams({ knowledge_base_id: knowledgeBaseId });
  return request<TraceList>(`/api/trace/${conversationId}?${params.toString()}`);
}