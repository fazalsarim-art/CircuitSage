import { useCallback, useEffect, useState } from "react";

import { listVersions } from "../features/benchmark/api";
import type { BenchmarkVersion } from "../features/benchmark/types";
import { listFeedback } from "../features/feedback/api";
import { FeedbackReview } from "../features/feedback/FeedbackReview";
import { FeedbackTable } from "../features/feedback/FeedbackTable";
import { FEEDBACK_STATUSES, type Feedback } from "../features/feedback/types";

export function FeedbackPage() {
  const [items, setItems] = useState<Feedback[] | null>(null);
  const [draftVersions, setDraftVersions] = useState<BenchmarkVersion[]>([]);
  const [selected, setSelected] = useState<Feedback | null>(null);
  const [statusFilter, setStatusFilter] = useState("");
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [feedbackResponse, versionResponse] = await Promise.all([
        listFeedback(statusFilter ? { status: statusFilter } : {}),
        listVersions(),
      ]);
      setItems(feedbackResponse.items);
      setDraftVersions(versionResponse.items.filter((v) => v.status === "draft"));
      setError(null);
    } catch {
      setError("Could not load feedback.");
      setItems([]);
    }
  }, [statusFilter]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return (
    <main className="page">
      <h1>Feedback</h1>
      <p className="empty-state">
        Review reader feedback on answers, attach corrected evidence, and — after review — promote a
        case into a draft benchmark version. Nothing enters the benchmark automatically.
      </p>

      <label htmlFor="feedback-status">Filter by status</label>{" "}
      <select
        id="feedback-status"
        value={statusFilter}
        onChange={(e) => setStatusFilter(e.target.value)}
      >
        <option value="">All</option>
        {FEEDBACK_STATUSES.map((s) => (
          <option key={s} value={s}>
            {s}
          </option>
        ))}
      </select>

      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {items === null && <p role="status">Loading feedback…</p>}
      {items !== null && items.length === 0 && (
        <p className="empty-state">No feedback in this view.</p>
      )}
      {items !== null && items.length > 0 && (
        <FeedbackTable items={items} selectedId={selected?.id ?? null} onSelect={setSelected} />
      )}

      {selected && (
        <FeedbackReview
          key={selected.id}
          feedbackId={selected.id}
          draftVersions={draftVersions}
          onReviewed={refresh}
        />
      )}
    </main>
  );
}
