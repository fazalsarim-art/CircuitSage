import { useState } from "react";

import { submitFeedback } from "./api";
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
  const assistant = response.assistant_message;

  async function rate(rating: 0 | 1) {
    try {
      await submitFeedback(assistant.id, rating);
      setFeedback("sent");
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
          <button type="button" aria-label="Helpful" onClick={() => void rate(1)}>
            👍
          </button>
          <button type="button" aria-label="Not helpful" onClick={() => void rate(0)}>
            👎
          </button>
          {feedback === "sent" && <span className="feedback-note">Thanks!</span>}
          {feedback === "error" && <span className="feedback-note">Could not save.</span>}
        </span>
      </div>
    </section>
  );
}
