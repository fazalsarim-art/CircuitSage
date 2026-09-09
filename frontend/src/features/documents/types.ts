export interface DocumentSummary {
  id: string;
  title: string;
  status: string;
  visibility: string;
  page_count: number | null;
  chunk_count: number;
  source_url: string | null;
  publisher: string | null;
  created_at: string;
  updated_at: string;
}

export interface DocumentListResponse {
  items: DocumentSummary[];
  next_cursor: string | null;
}

export interface ChunkPreview {
  id: string;
  ordinal: number;
  heading: string | null;
  page_start: number;
  page_end: number;
  token_count: number;
  preview: string;
}

export interface ChunkListResponse {
  items: ChunkPreview[];
  next_cursor: string | null;
}

export interface UploadResponse {
  document_id: string;
  job_id: string;
  status: string;
}

export const TERMINAL_STATUSES = new Set(["indexed", "failed", "deleted"]);
