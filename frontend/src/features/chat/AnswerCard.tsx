import { useState } from "react";

import { FEEDBACK_REASONS, submitFeedback } from "./api";
import type { ChatResponse } from "./types";

const STATUS_LABEL: Record<string, string> = {
  answered: "Answered",
  insufficient_evidence: "Insufficient evidence",
  generation_failed: "Generation unavailable",
};

export function AnswerCard({
  response,
  onShowDetails,
}: {
  response: ChatResponse;
  onShowDetails: () => void;
}) {
  const [feedback, setFeedback] = useState<null | "sent" | "error">(null);
  const [showReasons, setShowReasons] = useState(false);
  const [reason, setReason] = useState("retrieval_miss");
  const [comment, setComment] = useState("");
  const assistant = response.assistant_message;

  async function send(rating: 0 | 1, extra: { reason?: string; comment?: string } = {}) {
    try {
      await submitFeedback(assistant.id, rating, extra);
      setFeedback("sent");
      setShowReasons(false);
    } catch {
      setFeedback("error");
    }
  }

  return (
    <section className="answer-card" aria-label="Answer">
      <div className="answer-head">
        <span className={`badge answer-${response.answer_status}`}>
          {STATUS_LABEL[response.answer_status] ?? response.answer_status}
        </span>
        <span className="answer-mode">{assistant.retrieval_mode}</span>
      </div>

      {/* Model text is rendered as escaped text — never as HTML. */}
      <p className="answer-text">{assistant.content}</p>

      {response.sources.length > 0 && (
        <div className="sources">
          <h3>Sources</h3>
          <ul>
            {response.sources.map((source) => (
              <li key={source.chunk_id} className="source-card">
                <div className="source-meta">
                  <strong>{source.label}</strong> · {source.document_title} · pages{" "}
                  {source.page_start}–{source.page_end}
                </div>
                <p className="source-preview">{source.preview}</p>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="answer-actions">
        <button type="button" onClick={onShowDetails}>
          Retrieval details
        </button>
        <span className="feedback">
          Helpful?
          <button type="button" aria-label="Helpful" onClick={() => void send(1)}>
            👍
          </button>
          <button
            type="button"
            aria-label="Not helpful"
            onClick={() => {
              setShowReasons(true);
              setFeedback(null);
            }}
          >
            👎
          </button>
          {feedback === "sent" && <span className="feedback-note">Thanks!</span>}
          {feedback === "error" && <span className="feedback-note">Could not save.</span>}
        </span>
      </div>

      {showReasons && (
        <div className="feedback-form" role="group" aria-label="Report a problem">
          <label htmlFor="fb-reason">What went wrong?</label>
          <select id="fb-reason" value={reason} onChange={(e) => setReason(e.target.value)}>
            {FEEDBACK_REASONS.map((r) => (
              <option key={r} value={r}>
                {r.replace(/_/g, " ")}
              </option>
            ))}
          </select>
          <label htmlFor="fb-comment">Comment (optional)</label>
          <input
            id="fb-comment"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            maxLength={2000}
          />
          <button
            type="button"
            onClick={() => void send(0, { reason, comment: comment.trim() || undefined })}
          >
            Send feedback
          </button>
        </div>
      )}
    </section>
  );
}
