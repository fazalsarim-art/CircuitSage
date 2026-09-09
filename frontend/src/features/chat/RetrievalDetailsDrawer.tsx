import { useEffect, useState } from "react";

import { getRetrievalTrace } from "./api";
import type { RetrievalTrace } from "./types";

function fmt(value: number | null): string {
  return value === null ? "—" : value.toFixed(3);
}

export function RetrievalDetailsDrawer({
  messageId,
  onClose,
}: {
  messageId: string;
  onClose: () => void;
}) {
  const [trace, setTrace] = useState<RetrievalTrace | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    getRetrievalTrace(messageId)
      .then((data) => active && setTrace(data))
      .catch(() => active && setError("Could not load retrieval details."));
    return () => {
      active = false;
    };
  }, [messageId]);

  return (
    <aside className="drawer" role="dialog" aria-modal="true" aria-label="Retrieval details">
      <header className="drawer-header">
        <h2>Retrieval details {trace ? `(${trace.retrieval_mode})` : ""}</h2>
        <button type="button" onClick={onClose} aria-label="Close retrieval details">
          ✕
        </button>
      </header>
      {error && (
        <p role="alert" className="form-error">
          {error}
        </p>
      )}
      {!trace && !error && <p role="status">Loading…</p>}
      {trace && (
        <table className="trace-table">
          <thead>
            <tr>
              <th scope="col">Document</th>
              <th scope="col">Pages</th>
              <th scope="col">Lex</th>
              <th scope="col">Dense</th>
              <th scope="col">Fused</th>
              <th scope="col">Rerank</th>
              <th scope="col">In context</th>
            </tr>
          </thead>
          <tbody>
            {trace.results.map((row) => (
              <tr key={row.chunk_id} className={row.selected_for_context ? "selected" : undefined}>
                <td>{row.document_title}</td>
                <td>
                  {row.page_start}–{row.page_end}
                </td>
                <td>{fmt(row.lexical_score)}</td>
                <td>{fmt(row.dense_score)}</td>
                <td>{fmt(row.fused_score)}</td>
                <td>{fmt(row.rerank_score)}</td>
                <td>{row.selected_for_context ? "✓" : ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </aside>
  );
}
