import { useEffect, useState } from "react";

import { listChunks } from "./api";
import type { ChunkPreview, DocumentSummary } from "./types";

export function ChunkViewer({
  document,
  onClose,
}: {
  document: DocumentSummary;
  onClose: () => void;
}) {
  const [chunks, setChunks] = useState<ChunkPreview[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    listChunks(document.id)
      .then((response) => {
        if (active) {
          setChunks(response.items);
          setLoading(false);
        }
      })
      .catch(() => {
        if (active) {
          setError("Could not load chunks.");
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [document.id]);

  return (
    <div
      className="modal-overlay"
      role="dialog"
      aria-modal="true"
      aria-label={`Chunks for ${document.title}`}
    >
      <div className="modal">
        <header className="modal-header">
          <h2>{document.title} — chunks</h2>
          <button type="button" onClick={onClose} aria-label="Close chunk viewer">
            ✕
          </button>
        </header>
        {loading && <p role="status">Loading chunks…</p>}
        {error && (
          <p role="alert" className="form-error">
            {error}
          </p>
        )}
        {!loading && !error && chunks.length === 0 && <p>No chunks yet for this document.</p>}
        <ol className="chunk-list">
          {chunks.map((chunk) => (
            <li key={chunk.id}>
              <div className="chunk-meta">
                #{chunk.ordinal} · pages {chunk.page_start}–{chunk.page_end} · {chunk.token_count}{" "}
                tokens
                {chunk.heading ? ` · ${chunk.heading}` : ""}
              </div>
              <p className="chunk-preview">{chunk.preview}</p>
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}
