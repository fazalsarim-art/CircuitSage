import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import type { ApiError } from "../api/client";
import {
  createConversation,
  getConversation,
  listConversations,
  sendMessage,
} from "../features/chat/api";
import { AnswerCard } from "../features/chat/AnswerCard";
import { ConversationList } from "../features/chat/ConversationList";
import { QueryComposer, type ComposerSubmit } from "../features/chat/QueryComposer";
import { RetrievalDetailsDrawer } from "../features/chat/RetrievalDetailsDrawer";
import type { ChatResponse, ConversationSummary, MessageOut } from "../features/chat/types";

export function AskPage() {
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<MessageOut[]>([]);
  const [latest, setLatest] = useState<ChatResponse | null>(null);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<{ code: string; message: string } | null>(null);
  const [detailsFor, setDetailsFor] = useState<string | null>(null);

  const loadConversations = useCallback(async () => {
    try {
      const response = await listConversations();
      setConversations(response.items);
    } catch {
      // Non-fatal: the composer still works without the list.
    }
  }, []);

  useEffect(() => {
    void loadConversations();
  }, [loadConversations]);

  const selectConversation = useCallback(async (id: string) => {
    setActiveId(id);
    setLatest(null);
    setError(null);
    try {
      const conversation = await getConversation(id);
      setMessages(conversation.messages);
    } catch {
      setMessages([]);
    }
  }, []);

  function newConversation() {
    setActiveId(null);
    setMessages([]);
    setLatest(null);
    setError(null);
  }

  async function handleSubmit(value: ComposerSubmit) {
    setSending(true);
    setError(null);
    try {
      let conversationId = activeId;
      if (!conversationId) {
        const conversation = await createConversation(value.content.slice(0, 60));
        conversationId = conversation.id;
        setActiveId(conversation.id);
        await loadConversations();
      }
      const response = await sendMessage(conversationId, {
        content: value.content,
        retrieval_mode: value.retrieval_mode,
        top_k: value.top_k,
        reranker_enabled: value.reranker_enabled,
      });
      setMessages((prev) => [...prev, response.user_message, response.assistant_message]);
      setLatest(response);
    } catch (err) {
      const apiError = err as ApiError;
      setError({ code: apiError?.code ?? "error", message: apiError?.message ?? "Request failed." });
    } finally {
      setSending(false);
    }
  }

  return (
    <main className="page ask-page">
      <div className="ask-layout">
        <ConversationList
          conversations={conversations}
          activeId={activeId}
          onSelect={selectConversation}
          onNew={newConversation}
        />
        <div className="ask-main">
          <h1>Ask a debugging question</h1>

          <div className="messages">
            {messages
              .filter((message) => message.id !== latest?.assistant_message.id)
              .map((message) => (
                <div key={message.id} className={`message ${message.role}`}>
                  <div className="message-role">{message.role}</div>
                  <p>{message.content}</p>
                </div>
              ))}
          </div>

          {error?.code === "corpus_not_ready" ? (
            <p className="empty-state" role="alert">
              No indexed documents yet. <Link to="/documents">Upload documents</Link> to start
              asking.
            </p>
          ) : error?.code === "retrieval_unavailable" ? (
            <p className="form-error" role="alert">
              Retrieval is temporarily unavailable. Please try again.
            </p>
          ) : error ? (
            <p className="form-error" role="alert">
              {error.message}
            </p>
          ) : null}

          {latest && (
            <AnswerCard
              response={latest}
              onShowDetails={() => setDetailsFor(latest.assistant_message.id)}
            />
          )}

          <QueryComposer disabled={sending} onSubmit={handleSubmit} />
        </div>
      </div>
      {detailsFor && (
        <RetrievalDetailsDrawer messageId={detailsFor} onClose={() => setDetailsFor(null)} />
      )}
    </main>
  );
}
