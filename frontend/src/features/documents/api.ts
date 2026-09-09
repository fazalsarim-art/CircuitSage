import { apiJson } from "../../api/client";
import type {
  ChunkListResponse,
  DocumentListResponse,
  DocumentSummary,
  UploadResponse,
} from "./types";

export function listDocuments(params: { status?: string; search?: string } = {}) {
  const query = new URLSearchParams();
  if (params.status) query.set("status", params.status);
  if (params.search) query.set("search", params.search);
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return apiJson<DocumentListResponse>(`/documents${suffix}`);
}

export function getDocument(id: string) {
  return apiJson<DocumentSummary>(`/documents/${id}`);
}

export function uploadDocument(input: {
  file: File;
  title: string;
  visibility: string;
  sourceUrl?: string;
}) {
  const form = new FormData();
  form.set("file", input.file);
  form.set("title", input.title);
  form.set("visibility", input.visibility);
  if (input.sourceUrl) form.set("source_url", input.sourceUrl);
  return apiJson<UploadResponse>("/documents", { method: "POST", body: form });
}

export function listChunks(id: string, cursor?: string) {
  const suffix = cursor ? `?cursor=${encodeURIComponent(cursor)}` : "";
  return apiJson<ChunkListResponse>(`/documents/${id}/chunks${suffix}`);
}

export function reindexDocument(id: string) {
  return apiJson<UploadResponse>(`/documents/${id}/reindex`, { method: "POST", body: new FormData() });
}

export function deleteDocument(id: string) {
  return apiJson<{ document_id: string; status: string }>(`/documents/${id}`, { method: "DELETE" });
}
