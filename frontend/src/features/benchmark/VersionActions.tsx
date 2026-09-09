import { useState } from "react";

import type { ApiError } from "../../api/client";
import { exportCases, importCases, publishVersion } from "./api";
import type { BenchmarkVersion } from "./types";

interface Props {
  version: BenchmarkVersion;
  onChanged: () => void;
}

export function VersionActions({ version, onChanged }: Props) {
  const draft = version.status === "draft";
  const [file, setFile] = useState<File | null>(null);
  const [replace, setReplace] = useState(false);
  const [confirmation, setConfirmation] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleImport() {
    if (!file) {
      setError("Choose a JSONL file to import.");
      return;
    }
    setError(null);
    setMessage(null);
    setBusy(true);
    try {
      const result = await importCases(version.id, file, replace);
      setMessage(`Imported ${result.imported} cases (${result.judgments} judgments).`);
      setFile(null);
      onChanged();
    } catch (err) {
      setError((err as ApiError)?.message ?? "Import failed.");
    } finally {
      setBusy(false);
    }
  }

  async function handleExport() {
    setError(null);
    try {
      const text = await exportCases(version.id);
      const url = URL.createObjectURL(new Blob([text], { type: "application/x-ndjson" }));
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `${version.name}-v${version.version}.jsonl`;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch {
      setError("Export failed.");
    }
  }

  async function handlePublish() {
    setError(null);
    setMessage(null);
    setBusy(true);
    try {
      await publishVersion(version.id, { confirmation });
      setConfirmation("");
      onChanged();
    } catch (err) {
      setError((err as ApiError)?.message ?? "Publish failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="doc-upload" aria-label="Version actions">
      <h2>
        {version.name} v{version.version} — {version.status}
      </h2>
      {message && <p role="status">{message}</p>}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      <div className="doc-actions">
        <button type="button" onClick={handleExport}>
          Export JSONL
        </button>
      </div>

      {draft && (
        <>
          <label htmlFor="bench-import">Import JSONL question bank</label>
          <input
            id="bench-import"
            type="file"
            accept=".jsonl,application/x-ndjson,application/json"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
          <label className="checkbox">
            <input type="checkbox" checked={replace} onChange={(e) => setReplace(e.target.checked)} />
            Replace existing cases
          </label>
          <div className="doc-actions">
            <button type="button" onClick={handleImport} disabled={busy}>
              Import
            </button>
          </div>

          <label htmlFor="bench-confirm">
            Publish (type <strong>{version.name}</strong> to confirm — immutable afterwards)
          </label>
          <input
            id="bench-confirm"
            value={confirmation}
            onChange={(e) => setConfirmation(e.target.value)}
            placeholder={version.name}
          />
          <div className="doc-actions">
            <button
              type="button"
              onClick={handlePublish}
              disabled={busy || confirmation !== version.name}
            >
              Publish version
            </button>
          </div>
        </>
      )}
    </section>
  );
}
