export interface EvalMetrics {
  hit_at_5?: number;
  recall_at_5?: number;
  mrr_at_10?: number;
  ndcg_at_10?: number;
  p95_latency_ms?: number;
  case_count?: number;
  answerable_case_count?: number;
  errored_case_count?: number;
  ndcg_by_category?: Record<string, number>;
}

export interface EvalRun {
  id: string;
  benchmark_version_id: string;
  status: string;
  retrieval_mode: string;
  top_k: number;
  candidate_k: number;
  rrf_k: number;
  reranker_model: string | null;
  embedding_model: string;
  corpus_fingerprint: string;
  metrics: EvalMetrics | null;
  error_code: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface EvalRunListResponse {
  items: EvalRun[];
}

export interface EvalCaseResult {
  benchmark_case_id: string;
  hit_at_5: number | null;
  recall_at_5: number | null;
  reciprocal_rank: number | null;
  ndcg_at_10: number | null;
  latency_ms: number | null;
  error_code: string | null;
}

export interface EvalRunDetail {
  run: EvalRun;
  results: EvalCaseResult[];
}

export interface CompareResponse {
  left: EvalRun;
  right: EvalRun;
  equivalent: boolean;
  metric_deltas: Record<string, number>;
}

export const RETRIEVAL_MODES = ["lexical", "dense", "hybrid", "reranked_hybrid"] as const;

export const SCORE_METRICS = [
  { key: "hit_at_5", label: "Hit@5" },
  { key: "recall_at_5", label: "Recall@5" },
  { key: "mrr_at_10", label: "MRR@10" },
  { key: "ndcg_at_10", label: "nDCG@10" },
] as const;
