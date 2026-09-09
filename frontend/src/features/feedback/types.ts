export interface Correction {
  chunk_id: string;
  relevance: number;
  document_title: string | null;
  page_start: number | null;
  page_end: number | null;
}

export interface FeedbackEvent {
  id: string;
  action: string;
  actor_id: string | null;
  note: string | null;
  created_at: string;
}

export interface Feedback {
  id: string;
  message_id: string;
  user_id: string;
  rating: number;
  reason: string | null;
  comment: string | null;
  status: string;
  reviewed_by: string | null;
  reviewed_at: string | null;
  resolution_note: string | null;
  created_at: string;
  updated_at: string;
  question: string | null;
  answer: string | null;
  answer_status: string | null;
  retrieval_mode: string | null;
  corrections: Correction[];
}

export interface FeedbackDetail extends Feedback {
  events: FeedbackEvent[];
}

export interface FeedbackListResponse {
  items: Feedback[];
}

export interface CorrectionIn {
  chunk_id: string;
  relevance: number;
}

export interface DraftCaseSpec {
  benchmark_version_id: string;
  external_id: string;
  category: string;
  difficulty: string;
  split: string;
}

export interface ReviewRequest {
  status: string;
  resolution_note?: string;
  corrections?: CorrectionIn[];
  draft?: DraftCaseSpec;
}

export const FEEDBACK_STATUSES = ["unresolved", "resolved", "ignored", "promoted_to_draft"] as const;
