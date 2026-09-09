import { useEffect, useState } from "react";

import { compareRuns } from "./api";
import type { CompareResponse, EvalRun } from "./types";
import { SCORE_METRICS } from "./types";

interface Props {
  left: EvalRun;
  right: EvalRun;
}

function fmt(value: number): string {
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(3)}`;
}

export function ComparePanel({ left, right }: Props) {
  const [comparison, setComparison] = useState<CompareResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setComparison(null);
    setError(null);
    compareRuns(left.id, right.id)
      .then((data) => {
        if (active) setComparison(data);
      })
      .catch(() => {
        if (active) setError("These runs cannot be compared (different benchmark versions).");
      });
    return () => {
      active = false;
    };
  }, [left.id, right.id]);

  return (
    <section className="doc-upload" aria-label="Run comparison">
      <h2>
        Compare: {left.retrieval_mode} vs {right.retrieval_mode}
      </h2>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {!comparison && !error && <p role="status">Comparing…</p>}
      {comparison && (
        <>
          {!comparison.equivalent && (
            <p className="badge status-failed">
              Not directly comparable — corpus fingerprints differ.
            </p>
          )}
          <table className="trace-table">
            <caption className="sr-only">Metric deltas</caption>
            <thead>
              <tr>
                <th scope="col">Metric</th>
                <th scope="col">{left.retrieval_mode}</th>
                <th scope="col">{right.retrieval_mode}</th>
                <th scope="col">Δ</th>
              </tr>
            </thead>
            <tbody>
              {SCORE_METRICS.map(({ key, label }) => (
                <tr key={key}>
                  <th scope="row">{label}</th>
                  <td>{comparison.left.metrics?.[key]?.toFixed(3) ?? "—"}</td>
                  <td>{comparison.right.metrics?.[key]?.toFixed(3) ?? "—"}</td>
                  <td>{fmt(comparison.metric_deltas[key] ?? 0)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </section>
  );
}
