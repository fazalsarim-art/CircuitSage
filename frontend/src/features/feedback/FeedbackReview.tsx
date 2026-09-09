import { useCallback, useEffect, useMemo, useState } from "react";

import type { ApiError } from "../../api/client";
import type { BenchmarkVersion } from "../benchmark/types";
import type { RetrievalResultOut } from "../chat/types";
import { getFeedback, getRetrievalTrace, reviewFeedback } from "./api";
import type { CorrectionIn, FeedbackDetail } from "./types";

interface Props {
  feedbackId: string;
  draftVersions: BenchmarkVersion[];
  onReviewed: () => void;
}

const RELEVANCE_OPTIONS = [0, 1, 2, 3];

export function FeedbackReview({ feedbackId, draftVersions, onReviewed }: Props) {
  const [detail, setDetail] = useState<FeedbackDetail | null>(null);
  const [candidates, setCandidates] = useState<RetrievalResultOut[]>([]);
  const [grades, setGrades] = useState<Record<string, number>>({});
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Draft-case promotion fields.
  const [versionId, setVersionId] = useState("");
  const [externalId, setExternalId] = useState("");
  const [category, setCategory] = useState("retrieval_miss");
  const [difficulty, setDifficulty] = useState("medium");
  const [split, setSplit] = useState("test");

  const load = useCallback(async () => {
    setError(null);
    try {
      const feedback = await getFeedback(feedbackId);
      setDetail(feedback);
      setNote(feedback.resolution_note ?? "");
      const seeded: Record<string, number> = {};
      for (const correction of feedback.corrections) {
        seeded[correction.chunk_id] = correction.relevance;
      }
      setGrades(seeded);
      try {
        const trace = await getRetrievalTrace(feedback.message_id);
        setCandidates(trace.results);
      } catch {
        setCandidates([]); // trace is optional context
      }
    } catch {
      setError("Could not load feedback.");
    }
  }, [feedbackId]);

  useEffect(() => {
    void load();
  }, [load]);

  const corrections: CorrectionIn[] = useMemo(
    () =>
      Object.entries(grades)
        .filter(([, relevance]) => relevance >= 1)
        .map(([chunk_id, relevance]) => ({ chunk_id, relevance })),
    [grades],
  );

  async function submit(status: string, includeDraft: boolean) {
    setError(null);
    setBusy(true);
    try {
      await reviewFeedback(feedbackId, {
        status,
        resolution_note: note.trim() || undefined,
        corrections: corrections.length > 0 ? corrections : undefined,
        draft: includeDraft
          ? {
              benchmark_version_id: versionId,
              external_id: externalId.trim(),
              category: category.trim(),
              difficulty,
              split,
            }
          : undefined,
      });
      await load();
      onReviewed();
    } catch (err) {
      setError((err as ApiError)?.message ?? "Review failed.");
    } finally {
      setBusy(false);
    }
  }

  if (!detail) {
    return (
      <section className="doc-upload" aria-label="Feedback review">
        {error ? (
          <p className="form-error" role="alert">
            {error}
          </p>
        ) : (
          <p role="status">Loading…</p>
        )}
      </section>
    );
  }

  return (
    <section className="doc-upload" aria-label="Feedback review">
      <h2>Review feedback</h2>
      <p>
        <strong>Question:</strong> {detail.question ?? "—"}
      </p>
      <p>
        <strong>Answer:</strong> {detail.answer ?? "—"}
      </p>
      <p className="chunk-meta">
        {detail.rating === 1 ? "👍 helpful" : "👎 not helpful"}
        {detail.reason ? ` · ${detail.reason}` : ""} · status {detail.status}
      </p>
      {detail.comment && (
        <p>
          <strong>Comment:</strong> {detail.comment}
        </p>
      )}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}

      <h3>Corrected evidence</h3>
      {candidates.length === 0 ? (
        <p className="empty-state">No retrieved chunks recorded for this answer.</p>
      ) : (
        <table className="trace-table">
          <caption className="sr-only">Grade retrieved chunks</caption>
          <thead>
            <tr>
              <th scope="col">Document</th>
              <th scope="col">Pages</th>
              <th scope="col">Relevance</th>
            </tr>
          </thead>
          <tbody>
            {candidates.map((candidate) => (
              <tr key={candidate.chunk_id}>
                <td>{candidate.document_title}</td>
                <td>
                  {candidate.page_start}–{candidate.page_end}
                </td>
                <td>
                  <select
                    aria-label={`Relevance for ${candidate.document_title} p${candidate.page_start}`}
                    value={grades[candidate.chunk_id] ?? 0}
                    onChange={(e) =>
                      setGrades((g) => ({ ...g, [candidate.chunk_id]: Number(e.target.value) }))
                    }
                  >
                    {RELEVANCE_OPTIONS.map((n) => (
                      <option key={n} value={n}>
                        {n === 0 ? "0 (omit)" : n}
                      </option>
                    ))}
                  </select>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <label htmlFor="review-note">Resolution note</label>
      <input id="review-note" value={note} onChange={(e) => setNote(e.target.value)} />

      <div className="doc-actions">
        <button type="button" onClick={() => void submit("resolved", false)} disabled={busy}>
          Resolve
        </button>
        <button type="button" onClick={() => void submit("ignored", false)} disabled={busy}>
          Ignore
        </button>
      </div>

      <h3>Promote to draft benchmark case</h3>
      {draftVersions.length === 0 ? (
        <p className="empty-state">
          No draft benchmark version available. Create one on the Benchmark page first.
        </p>
      ) : (
        <>
          <p className="chunk-meta">
            Files the question plus graded evidence as a draft case (admin action — never automatic).
          </p>
          <label htmlFor="promote-version">Draft version</label>
          <select
            id="promote-version"
            value={versionId}
            onChange={(e) => setVersionId(e.target.value)}
          >
            <option value="">Select…</option>
            {draftVersions.map((v) => (
              <option key={v.id} value={v.id}>
                {v.name} v{v.version}
              </option>
            ))}
          </select>
          <label htmlFor="promote-external">External ID</label>
          <input
            id="promote-external"
            value={externalId}
            onChange={(e) => setExternalId(e.target.value)}
            placeholder="fb-spi-1"
          />
          <label htmlFor="promote-category">Category</label>
          <input
            id="promote-category"
            value={category}
            onChange={(e) => setCategory(e.target.value)}
          />
          <div className="composer-controls">
            <label>
              Difficulty
              <select value={difficulty} onChange={(e) => setDifficulty(e.target.value)}>
                <option value="easy">easy</option>
                <option value="medium">medium</option>
                <option value="hard">hard</option>
              </select>
            </label>
            <label>
              Split
              <select value={split} onChange={(e) => setSplit(e.target.value)}>
                <option value="train">train</option>
                <option value="validation">validation</option>
                <option value="test">test</option>
              </select>
            </label>
          </div>
          <div className="doc-actions">
            <button
              type="button"
              onClick={() => void submit("promoted_to_draft", true)}
              disabled={busy || !versionId || !externalId.trim() || corrections.length === 0}
            >
              Promote to draft
            </button>
          </div>
        </>
      )}

      <h3>Audit history</h3>
      <ul className="chunk-list">
        {detail.events.map((event) => (
          <li key={event.id} className="chunk-meta">
            {new Date(event.created_at).toLocaleString()} — {event.action}
            {event.note ? `: ${event.note}` : ""}
          </li>
        ))}
      </ul>
    </section>
  );
}
