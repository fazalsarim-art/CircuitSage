import { useEffect, useState } from "react";

import { getRun } from "./api";
import { MetricsGrid } from "./MetricsGrid";
import type { EvalRunDetail } from "./types";

interface Props {
  runId: string;
  onClose: () => void;
}

export function RunDetail({ runId, onClose }: Props) {
  const [detail, setDetail] = useState<EvalRunDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    getRun(runId)
      .then((data) => {
        if (active) setDetail(data);
      })
      .catch(() => {
        if (active) setError("Could not load run.");
      });
    return () => {
      active = false;
    };
  }, [runId]);

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true" aria-label="Run detail">
      <div className="modal drawer">
        <div className="modal-header">
          <h2>Run detail</h2>
          <button type="button" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        {!detail && !error && <p role="status">Loading…</p>}
        {detail && (
          <>
            <p>
              <strong>{detail.run.retrieval_mode}</strong> · {detail.run.status} · embedding{" "}
              {detail.run.embedding_model}
            </p>
            <p className="chunk-meta">corpus {detail.run.corpus_fingerprint.slice(0, 12)}…</p>
            <MetricsGrid metrics={detail.run.metrics} />
            <h3>Per-case results ({detail.results.length})</h3>
            <table className="trace-table">
              <caption className="sr-only">Per-case results</caption>
              <thead>
                <tr>
                  <th scope="col">Case</th>
                  <th scope="col">Hit@5</th>
                  <th scope="col">Recall@5</th>
                  <th scope="col">RR</th>
                  <th scope="col">nDCG@10</th>
                  <th scope="col">Latency</th>
                </tr>
              </thead>
              <tbody>
                {detail.results.map((result) => (
                  <tr key={result.benchmark_case_id}>
                    <td>{result.benchmark_case_id.slice(0, 8)}</td>
                    {result.error_code ? (
                      <td colSpan={5}>
                        <span className="badge status-failed">{result.error_code}</span>
                      </td>
                    ) : (
                      <>
                        <td>{result.hit_at_5?.toFixed(2) ?? "—"}</td>
                        <td>{result.recall_at_5?.toFixed(2) ?? "—"}</td>
                        <td>{result.reciprocal_rank?.toFixed(2) ?? "—"}</td>
                        <td>{result.ndcg_at_10?.toFixed(3) ?? "—"}</td>
                        <td>{result.latency_ms ?? "—"} ms</td>
                      </>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </div>
    </div>
  );
}
