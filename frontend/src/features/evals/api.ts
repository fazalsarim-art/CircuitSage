import { apiFetch, apiJson } from "../../api/client";
import type {
  CompareResponse,
  EvalRun,
  EvalRunDetail,
  EvalRunListResponse,
} from "./types";

export function listRuns(params: { benchmark_version_id?: string; status?: string } = {}) {
  const query = new URLSearchParams();
  if (params.benchmark_version_id) query.set("benchmark_version_id", params.benchmark_version_id);
  if (params.status) query.set("status", params.status);
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return apiJson<EvalRunListResponse>(`/evals/runs${suffix}`);
}

export function createRun(input: {
  benchmark_version_id: string;
  retrieval_mode: string;
  top_k?: number;
  reranker_enabled?: boolean;
}) {
  return apiJson<EvalRun>("/evals/runs", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function getRun(runId: string) {
  return apiJson<EvalRunDetail>(`/evals/runs/${runId}`);
}

export function cancelRun(runId: string) {
  return apiJson<EvalRun>(`/evals/runs/${runId}/cancel`, { method: "POST" });
}

export function compareRuns(leftId: string, rightId: string) {
  return apiJson<CompareResponse>(
    `/evals/runs/compare?left_id=${encodeURIComponent(leftId)}&right_id=${encodeURIComponent(rightId)}`,
  );
}

export async function exportRun(runId: string): Promise<unknown> {
  const response = await apiFetch(`/evals/runs/${runId}/export`);
  if (!response.ok) {
    throw new Error("Export failed");
  }
  return response.json();
}
