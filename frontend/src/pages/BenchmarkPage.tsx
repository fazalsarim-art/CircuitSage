import { useCallback, useEffect, useState } from "react";

import { deleteCase, listCases, listVersions } from "../features/benchmark/api";
import { CaseTable } from "../features/benchmark/CaseTable";
import { CreateVersionForm } from "../features/benchmark/CreateVersionForm";
import type { BenchmarkCase, BenchmarkVersion } from "../features/benchmark/types";
import { VersionActions } from "../features/benchmark/VersionActions";
import { VersionList } from "../features/benchmark/VersionList";
import { useAuth } from "../features/auth/AuthContext";

export function BenchmarkPage() {
  const { isAdmin } = useAuth();
  const [versions, setVersions] = useState<BenchmarkVersion[] | null>(null);
  const [selected, setSelected] = useState<BenchmarkVersion | null>(null);
  const [cases, setCases] = useState<BenchmarkCase[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refreshVersions = useCallback(async () => {
    try {
      const response = await listVersions();
      setVersions(response.items);
      setError(null);
      return response.items;
    } catch {
      setError("Could not load benchmark versions.");
      setVersions([]);
      return [];
    }
  }, []);

  const refreshCases = useCallback(async (versionId: string) => {
    try {
      const response = await listCases(versionId);
      setCases(response.items);
    } catch {
      setError("Could not load cases.");
      setCases([]);
    }
  }, []);

  useEffect(() => {
    void refreshVersions();
  }, [refreshVersions]);

  useEffect(() => {
    if (selected) {
      void refreshCases(selected.id);
    } else {
      setCases(null);
    }
  }, [selected, refreshCases]);

  // Keep the selected version object in sync with the latest list (status/case_count).
  const syncSelection = useCallback(async () => {
    const items = await refreshVersions();
    if (selected) {
      const updated = items.find((v) => v.id === selected.id) ?? null;
      setSelected(updated);
      if (updated) {
        await refreshCases(updated.id);
      }
    }
  }, [refreshVersions, refreshCases, selected]);

  async function handleDeleteCase(benchmarkCase: BenchmarkCase) {
    if (!selected) return;
    if (!window.confirm(`Delete case "${benchmarkCase.external_id}"?`)) {
      return;
    }
    try {
      await deleteCase(benchmarkCase.id);
      await syncSelection();
    } catch {
      setError("Delete failed.");
    }
  }

  return (
    <main className="page">
      <h1>Benchmark</h1>
      <p className="empty-state">
        Graded relevance judgments used to measure retrieval. Import a question bank, label the
        relevant chunks per case, then publish an immutable version to evaluate against.
      </p>
      {isAdmin && <CreateVersionForm onCreated={refreshVersions} />}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {versions === null && <p role="status">Loading versions…</p>}
      {versions !== null && versions.length === 0 && (
        <p className="empty-state">No benchmark versions yet.</p>
      )}
      {versions !== null && versions.length > 0 && (
        <VersionList versions={versions} selectedId={selected?.id ?? null} onSelect={setSelected} />
      )}

      {selected && (
        <>
          {isAdmin && <VersionActions version={selected} onChanged={syncSelection} />}
          <h2>Cases in {selected.name} v{selected.version}</h2>
          {cases === null && <p role="status">Loading cases…</p>}
          {cases !== null && cases.length === 0 && (
            <p className="empty-state">No cases in this version yet.</p>
          )}
          {cases !== null && cases.length > 0 && (
            <CaseTable
              cases={cases}
              isAdmin={isAdmin}
              editable={selected.status === "draft"}
              onDelete={handleDeleteCase}
            />
          )}
        </>
      )}
    </main>
  );
}
