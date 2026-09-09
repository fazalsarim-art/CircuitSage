export interface Judgment {
  chunk_id: string;
  relevance: number;
  rationale: string | null;
}

export interface BenchmarkCase {
  id: string;
  external_id: string;
  question: string;
  category: string;
  difficulty: string;
  split: string;
  expected_answer: string | null;
  notes: string | null;
  judgments: Judgment[];
}

export interface BenchmarkVersion {
  id: string;
  name: string;
  version: number;
  status: string;
  description: string | null;
  published_at: string | null;
  source_commit: string | null;
  created_at: string;
  case_count: number;
}

export interface VersionListResponse {
  items: BenchmarkVersion[];
}

export interface CaseListResponse {
  items: BenchmarkCase[];
}

export interface ImportResult {
  imported: number;
  judgments: number;
}

export const DIFFICULTIES = ["easy", "medium", "hard"] as const;
export const SPLITS = ["train", "validation", "test"] as const;
