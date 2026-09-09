export interface ConversationSummary {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface MessageOut {
  id: string;
  role: string;
  content: string;
  answer_status: string | null;
  retrieval_mode: string | null;
  created_at: string;
}

export interface Source {
  label: string;
  chunk_id: string;
  document_id: string;
  document_title: string;
  page_start: number;
  page_end: number;
  preview: string;
}

export interface ChatResponse {
  user_message: MessageOut;
  assistant_message: MessageOut;
  answer_status: string;
  sources: Source[];
  timings_ms: Record<string, number>;
}

export interface RetrievalResultOut {
  chunk_id: string;
  document_id: string;
  document_title: string;
  page_start: number;
  page_end: number;
  lexical_rank: number | null;
  dense_rank: number | null;
  fused_rank: number | null;
  rerank_rank: number | null;
  lexical_score: number | null;
  dense_score: number | null;
  fused_score: number | null;
  rerank_score: number | null;
  selected_for_context: boolean;
}

export interface RetrievalTrace {
  message_id: string;
  retrieval_mode: string | null;
  results: RetrievalResultOut[];
}

export const RETRIEVAL_MODES = ["hybrid", "reranked_hybrid", "dense", "lexical"] as const;
