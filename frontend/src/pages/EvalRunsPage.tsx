import { useCallback, useEffect, useRef, useState } from "react";

import { listVersions } from "../features/benchmark/api";
import type { BenchmarkVersion } from "../features/benchmark/types";
import { listRuns } from "../features/evals/api";
import { ComparePanel } from "../features/evals/ComparePanel";
import { CreateRunForm } from "../features/evals/CreateRunForm";
import { RunDetail } from "../features/evals/RunDetail";
import { RunTable } from "../features/evals/RunTable";
import type { EvalRun } from "../features/evals/types";
import { useAuth } from "../features/auth/AuthContext";

const ACTIVE = new Set(["queued", "running"]);

export function EvalRunsPage() {
  const { isAdmin } = useAuth();
  const [runs, setRuns] = useState<EvalRun[] | null>(null);
  const [versions, setVersions] = useState<BenchmarkVersion[]>([]);
  const [selected, setSelected] = useState<EvalRun[]>([]);
  const [detailId, setDetailId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<number | undefined>(undefined);

  const refresh = useCallback(async () => {
    try {
      const [runResponse, versionResponse] = await Promise.all([listRuns(), listVersions()]);
      setRuns(runResponse.items);
      setVersions(versionResponse.items);
      setError(null);
    } catch {
      setError("Could not load evaluation runs.");
      setRuns([]);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  // Poll every 3s while any run is queued or running.
  useEffect(() => {
    const active = runs?.some((run) => ACTIVE.has(run.status));
    if (!active) {
      return;
    }
    pollRef.current = window.setTimeout(() => void refresh(), 3000);
    return () => window.clearTimeout(pollRef.current);
  }, [runs, refresh]);

  function toggleSelection(run: EvalRun) {
    setSelected((current) => {
      if (current.some((r) => r.id === run.id)) {
        return current.filter((r) => r.id !== run.id);
      }
      if (current.length >= 2) {
        return current;
      }
      return [...current, run];
    });
  }

  const publishedVersions = versions.filter((v) => v.status === "published");

  return (
    <main className="page">
      <h1>Evaluation runs</h1>
      <p className="empty-state">
        Run retrieval over a published benchmark and compare modes on Hit@5, Recall@5, MRR@10, and
        nDCG@10. Select two runs to see the deltas.
      </p>
      {isAdmin && <CreateRunForm publishedVersions={publishedVersions} onCreated={refresh} />}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {runs === null && <p role="status">Loading runs…</p>}
      {runs !== null && runs.length === 0 && <p className="empty-state">No evaluation runs yet.</p>}
      {runs !== null && runs.length > 0 && (
        <RunTable
          runs={runs}
          selectedIds={selected.map((r) => r.id)}
          onToggle={toggleSelection}
          onOpen={(run) => setDetailId(run.id)}
        />
      )}

      {selected.length === 2 && <ComparePanel left={selected[0]} right={selected[1]} />}

      {detailId && <RunDetail runId={detailId} onClose={() => setDetailId(null)} />}
    </main>
  );
}
