import type { EvalRun } from "./types";

interface Props {
  runs: EvalRun[];
  selectedIds: string[];
  onToggle: (run: EvalRun) => void;
  onOpen: (run: EvalRun) => void;
}

const RUNNING = new Set(["queued", "running"]);

function statusClass(status: string): string {
  if (status === "succeeded") return "status-indexed";
  if (status === "failed" || status === "cancelled") return "status-failed";
  return "status-processing";
}

export function RunTable({ runs, selectedIds, onToggle, onOpen }: Props) {
  return (
    <table className="doc-table">
      <caption className="sr-only">Evaluation runs</caption>
      <thead>
        <tr>
          <th scope="col">Compare</th>
          <th scope="col">Mode</th>
          <th scope="col">Status</th>
          <th scope="col">nDCG@10</th>
          <th scope="col">MRR@10</th>
          <th scope="col">Created</th>
          <th scope="col" />
        </tr>
      </thead>
      <tbody>
        {runs.map((run) => (
          <tr key={run.id}>
            <td>
              <input
                type="checkbox"
                aria-label={`Select run ${run.retrieval_mode}`}
                checked={selectedIds.includes(run.id)}
                disabled={!selectedIds.includes(run.id) && selectedIds.length >= 2}
                onChange={() => onToggle(run)}
              />
            </td>
            <td>{run.retrieval_mode}</td>
            <td>
              <span className={`badge ${statusClass(run.status)}`}>
                {run.status}
                {RUNNING.has(run.status) ? "…" : ""}
              </span>
            </td>
            <td>{run.metrics?.ndcg_at_10?.toFixed(3) ?? "—"}</td>
            <td>{run.metrics?.mrr_at_10?.toFixed(3) ?? "—"}</td>
            <td>{new Date(run.created_at).toLocaleString()}</td>
            <td>
              <button type="button" onClick={() => onOpen(run)}>
                Details
              </button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
