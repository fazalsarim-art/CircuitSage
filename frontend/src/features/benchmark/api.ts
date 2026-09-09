import { apiFetch, apiJson } from "../../api/client";
import type {
  BenchmarkCase,
  BenchmarkVersion,
  CaseListResponse,
  ImportResult,
  VersionListResponse,
} from "./types";

export function listVersions() {
  return apiJson<VersionListResponse>("/benchmark/versions");
}

export function createVersion(input: { name: string; description?: string }) {
  return apiJson<BenchmarkVersion>("/benchmark/versions", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function listCases(versionId: string) {
  return apiJson<CaseListResponse>(`/benchmark/versions/${versionId}/cases`);
}

export function publishVersion(versionId: string, input: { confirmation: string; source_commit?: string }) {
  return apiJson<BenchmarkVersion>(`/benchmark/versions/${versionId}/publish`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function importCases(versionId: string, file: File, replace: boolean) {
  const form = new FormData();
  form.set("file", file);
  form.set("replace", String(replace));
  return apiJson<ImportResult>(`/benchmark/versions/${versionId}/import`, {
    method: "POST",
    body: form,
  });
}

export function deleteCase(caseId: string) {
  return apiFetch(`/benchmark/cases/${caseId}`, { method: "DELETE" });
}

export async function exportCases(versionId: string): Promise<string> {
  const response = await apiFetch(`/benchmark/versions/${versionId}/export`);
  if (!response.ok) {
    throw new Error("Export failed");
  }
  return response.text();
}

export type { BenchmarkCase };
