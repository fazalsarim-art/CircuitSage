import { useCallback, useEffect, useRef, useState } from "react";

import { useAuth } from "../features/auth/AuthContext";
import { deleteDocument, listDocuments, reindexDocument } from "../features/documents/api";
import { ChunkViewer } from "../features/documents/ChunkViewer";
import { DocumentUpload } from "../features/documents/DocumentUpload";
import { DocumentsTable } from "../features/documents/DocumentsTable";
import { TERMINAL_STATUSES, type DocumentSummary } from "../features/documents/types";

export function DocumentsPage() {
  const { isAdmin } = useAuth();
  const [documents, setDocuments] = useState<DocumentSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [viewing, setViewing] = useState<DocumentSummary | null>(null);
  const pollRef = useRef<number | undefined>(undefined);

  const refresh = useCallback(async () => {
    try {
      const response = await listDocuments();
      setDocuments(response.items);
      setError(null);
    } catch {
      setError("Could not load documents.");
      setDocuments([]);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  // Poll every 3s while any document is still being processed.
  useEffect(() => {
    const pending = documents?.some((doc) => !TERMINAL_STATUSES.has(doc.status));
    if (!pending) {
      return;
    }
    pollRef.current = window.setTimeout(() => void refresh(), 3000);
    return () => window.clearTimeout(pollRef.current);
  }, [documents, refresh]);

  async function handleReindex(doc: DocumentSummary) {
    try {
      await reindexDocument(doc.id);
      await refresh();
    } catch {
      setError("Reindex failed.");
    }
  }

  async function handleDelete(doc: DocumentSummary) {
    if (!window.confirm(`Delete "${doc.title}"? This removes its chunks and vectors.`)) {
      return;
    }
    try {
      await deleteDocument(doc.id);
      await refresh();
    } catch {
      setError("Delete failed.");
    }
  }

  return (
    <main className="page documents-page">
      <h1>Documents</h1>
      {isAdmin && <DocumentUpload onUploaded={refresh} />}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {documents === null && <p role="status">Loading documents…</p>}
      {documents !== null && documents.length === 0 && (
        <p className="empty-state">
          No documents yet.{isAdmin ? " Upload a PDF above to get started." : ""}
        </p>
      )}
      {documents !== null && documents.length > 0 && (
        <DocumentsTable
          documents={documents}
          isAdmin={isAdmin}
          onViewChunks={setViewing}
          onReindex={handleReindex}
          onDelete={handleDelete}
        />
      )}
      {viewing && <ChunkViewer document={viewing} onClose={() => setViewing(null)} />}
    </main>
  );
}
