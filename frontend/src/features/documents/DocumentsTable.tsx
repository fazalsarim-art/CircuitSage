import type { DocumentSummary } from "./types";

interface Props {
  documents: DocumentSummary[];
  isAdmin: boolean;
  onViewChunks: (document: DocumentSummary) => void;
  onReindex: (document: DocumentSummary) => void;
  onDelete: (document: DocumentSummary) => void;
}

export function DocumentsTable({ documents, isAdmin, onViewChunks, onReindex, onDelete }: Props) {
  return (
    <table className="doc-table">
      <caption className="sr-only">Uploaded documents</caption>
      <thead>
        <tr>
          <th scope="col">Title</th>
          <th scope="col">Status</th>
          <th scope="col">Pages</th>
          <th scope="col">Chunks</th>
          <th scope="col">Visibility</th>
          <th scope="col">Actions</th>
        </tr>
      </thead>
      <tbody>
        {documents.map((doc) => (
          <tr key={doc.id}>
            <td>{doc.title}</td>
            <td>
              <span className={`badge status-${doc.status}`}>{doc.status}</span>
            </td>
            <td>{doc.page_count ?? "—"}</td>
            <td>{doc.chunk_count}</td>
            <td>{doc.visibility}</td>
            <td className="doc-actions">
              <button type="button" onClick={() => onViewChunks(doc)}>
                View chunks
              </button>
              {isAdmin && (
                <button
                  type="button"
                  onClick={() => onReindex(doc)}
                  disabled={doc.status !== "indexed" && doc.status !== "failed"}
                >
                  Reindex
                </button>
              )}
              {isAdmin && (
                <button type="button" className="danger" onClick={() => onDelete(doc)}>
                  Delete
                </button>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
