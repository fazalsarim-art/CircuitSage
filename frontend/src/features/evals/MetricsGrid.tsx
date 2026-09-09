import type { EvalMetrics } from "./types";
import { SCORE_METRICS } from "./types";

function fmt(value: number | undefined): string {
  return value === undefined ? "—" : value.toFixed(3);
}

export function MetricsGrid({ metrics }: { metrics: EvalMetrics | null }) {
  if (!metrics) {
    return <p className="empty-state">No metrics yet — the run has not completed.</p>;
  }
  const byCategory = Object.entries(metrics.ndcg_by_category ?? {});
  return (
    <div className="metrics-grid">
      <table className="trace-table">
        <caption className="sr-only">Aggregate metrics</caption>
        <tbody>
          {SCORE_METRICS.map(({ key, label }) => (
            <tr key={key}>
              <th scope="row">{label}</th>
              <td>{fmt(metrics[key])}</td>
            </tr>
          ))}
          <tr>
            <th scope="row">p95 latency</th>
            <td>{metrics.p95_latency_ms === undefined ? "—" : `${metrics.p95_latency_ms} ms`}</td>
          </tr>
          <tr>
            <th scope="row">Answerable cases</th>
            <td>
              {metrics.answerable_case_count ?? "—"} / {metrics.case_count ?? "—"}
              {metrics.errored_case_count ? ` (${metrics.errored_case_count} errored)` : ""}
            </td>
          </tr>
        </tbody>
      </table>
      {byCategory.length > 0 && (
        <table className="trace-table">
          <caption className="sr-only">nDCG by category</caption>
          <thead>
            <tr>
              <th scope="col">Category</th>
              <th scope="col">nDCG@10</th>
            </tr>
          </thead>
          <tbody>
            {byCategory.map(([category, value]) => (
              <tr key={category}>
                <th scope="row">{category}</th>
                <td>{fmt(value)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
