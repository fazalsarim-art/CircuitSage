import { apiJson } from "../../api/client";
import type { RetrievalTrace } from "../chat/types";
import type {
  FeedbackDetail,
  FeedbackListResponse,
  ReviewRequest,
} from "./types";

export function listFeedback(params: { status?: string; reason?: string; rating?: number } = {}) {
  const query = new URLSearchParams();
  if (params.status) query.set("status", params.status);
  if (params.reason) query.set("reason", params.reason);
  if (params.rating !== undefined) query.set("rating", String(params.rating));
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return apiJson<FeedbackListResponse>(`/feedback${suffix}`);
}

export function getFeedback(id: string) {
  return apiJson<FeedbackDetail>(`/feedback/${id}`);
}

export function reviewFeedback(id: string, body: ReviewRequest) {
  return apiJson<FeedbackDetail>(`/feedback/${id}/review`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function listReasons() {
  return apiJson<{ reasons: string[] }>("/feedback/reasons");
}

export function getRetrievalTrace(messageId: string) {
  return apiJson<RetrievalTrace>(`/messages/${messageId}/retrieval`);
}
