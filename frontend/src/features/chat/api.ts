import { apiJson } from "../../api/client";
import type { ChatResponse, ConversationSummary, MessageOut, RetrievalTrace } from "./types";

export function listConversations() {
  return apiJson<{ items: ConversationSummary[]; next_cursor: string | null }>("/conversations");
}

export function createConversation(title?: string) {
  return apiJson<ConversationSummary>("/conversations", {
    method: "POST",
    body: JSON.stringify({ title: title ?? null }),
  });
}

export function getConversation(id: string) {
  return apiJson<{ id: string; title: string; messages: MessageOut[] }>(`/conversations/${id}`);
}

export function sendMessage(
  conversationId: string,
  body: { content: string; retrieval_mode: string; top_k: number; reranker_enabled?: boolean },
) {
  return apiJson<ChatResponse>(`/conversations/${conversationId}/messages`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function getRetrievalTrace(messageId: string) {
  return apiJson<RetrievalTrace>(`/messages/${messageId}/retrieval`);
}

export function submitFeedback(messageId: string, rating: 0 | 1) {
  return apiJson<unknown>(`/messages/${messageId}/feedback`, {
    method: "PUT",
    body: JSON.stringify({ rating }),
  });
}
