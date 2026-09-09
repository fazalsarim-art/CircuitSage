import type { BenchmarkCase } from "./types";

interface Props {
  cases: BenchmarkCase[];
  isAdmin: boolean;
  editable: boolean;
  onDelete: (benchmarkCase: BenchmarkCase) => void;
}

function maxRelevance(benchmarkCase: BenchmarkCase): number {
  return benchmarkCase.judgments.reduce((max, j) => Math.max(max, j.relevance), 0);
}

export function CaseTable({ cases, isAdmin, editable, onDelete }: Props) {
  return (
    <table className="doc-table">
      <caption className="sr-only">Benchmark cases</caption>
      <thead>
        <tr>
          <th scope="col">External ID</th>
          <th scope="col">Question</th>
          <th scope="col">Category</th>
          <th scope="col">Difficulty</th>
          <th scope="col">Split</th>
          <th scope="col">Judgments</th>
          {isAdmin && editable && <th scope="col" />}
        </tr>
      </thead>
      <tbody>
        {cases.map((benchmarkCase) => {
          const labelled = benchmarkCase.judgments.length > 0;
          const answerable = benchmarkCase.category !== "unanswerable";
          const needsLabel = answerable && maxRelevance(benchmarkCase) < 2;
          return (
            <tr key={benchmarkCase.id}>
              <td>{benchmarkCase.external_id}</td>
              <td>{benchmarkCase.question}</td>
              <td>{benchmarkCase.category}</td>
              <td>{benchmarkCase.difficulty}</td>
              <td>{benchmarkCase.split}</td>
              <td>
                {labelled ? (
                  <span className="badge status-indexed">{benchmarkCase.judgments.length} labelled</span>
                ) : (
                  <span className={`badge status-${needsLabel ? "failed" : "queued"}`}>
                    {answerable ? "unlabelled" : "unanswerable"}
                  </span>
                )}
              </td>
              {isAdmin && editable && (
                <td className="doc-actions">
                  <button type="button" className="danger" onClick={() => onDelete(benchmarkCase)}>
                    Delete
                  </button>
                </td>
              )}
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
