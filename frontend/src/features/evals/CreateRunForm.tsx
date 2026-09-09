import { useState, type FormEvent } from "react";

import type { ApiError } from "../../api/client";
import type { BenchmarkVersion } from "../benchmark/types";
import { createRun } from "./api";
import { RETRIEVAL_MODES } from "./types";

interface Props {
  publishedVersions: BenchmarkVersion[];
  onCreated: () => void;
}

export function CreateRunForm({ publishedVersions, onCreated }: Props) {
  const [versionId, setVersionId] = useState("");
  const [mode, setMode] = useState<string>("hybrid");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!versionId) {
      setError("Select a published benchmark version.");
      return;
    }
    setError(null);
    setBusy(true);
    try {
      await createRun({ benchmark_version_id: versionId, retrieval_mode: mode });
      onCreated();
    } catch (err) {
      setError((err as ApiError)?.message ?? "Could not queue run.");
    } finally {
      setBusy(false);
    }
  }

  if (publishedVersions.length === 0) {
    return (
      <p className="empty-state">
        No published benchmark versions yet. Publish one on the Benchmark page to run an evaluation.
      </p>
    );
  }

  return (
    <form className="doc-upload" onSubmit={handleSubmit} aria-label="Queue evaluation run">
      <h2>Queue an evaluation run</h2>
      <label htmlFor="run-version">Benchmark version</label>
      <select id="run-version" value={versionId} onChange={(e) => setVersionId(e.target.value)}>
        <option value="">Select…</option>
        {publishedVersions.map((v) => (
          <option key={v.id} value={v.id}>
            {v.name} v{v.version} ({v.case_count} cases)
          </option>
        ))}
      </select>
      <label htmlFor="run-mode">Retrieval mode</label>
      <select id="run-mode" value={mode} onChange={(e) => setMode(e.target.value)}>
        {RETRIEVAL_MODES.map((m) => (
          <option key={m} value={m}>
            {m}
          </option>
        ))}
      </select>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      <button type="submit" disabled={busy}>
        {busy ? "Queuing…" : "Queue run"}
      </button>
    </form>
  );
}
