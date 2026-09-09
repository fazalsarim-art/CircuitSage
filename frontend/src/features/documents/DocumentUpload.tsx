import { useState, type FormEvent } from "react";

import type { ApiError } from "../../api/client";
import { uploadDocument } from "./api";

export function DocumentUpload({ onUploaded }: { onUploaded: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [visibility, setVisibility] = useState("private");
  const [sourceUrl, setSourceUrl] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!file) {
      setError("Choose a PDF file to upload.");
      return;
    }
    setError(null);
    setBusy(true);
    try {
      await uploadDocument({
        file,
        title: title.trim() || file.name,
        visibility,
        sourceUrl: sourceUrl.trim() || undefined,
      });
      setFile(null);
      setTitle("");
      setSourceUrl("");
      onUploaded();
    } catch (err) {
      setError((err as ApiError)?.message ?? "Upload failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="doc-upload" onSubmit={handleSubmit} aria-label="Upload document">
      <h2>Upload a PDF</h2>
      <label htmlFor="doc-file">PDF file</label>
      <input
        id="doc-file"
        type="file"
        accept="application/pdf"
        onChange={(e) => setFile(e.target.files?.[0] ?? null)}
      />
      <label htmlFor="doc-title">Title</label>
      <input
        id="doc-title"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        placeholder="Defaults to the filename"
      />
      <label htmlFor="doc-source">Source URL (optional)</label>
      <input id="doc-source" value={sourceUrl} onChange={(e) => setSourceUrl(e.target.value)} />
      <label htmlFor="doc-visibility">Visibility</label>
      <select id="doc-visibility" value={visibility} onChange={(e) => setVisibility(e.target.value)}>
        <option value="private">Private</option>
        <option value="shared">Shared</option>
      </select>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      <button type="submit" disabled={busy || !file}>
        {busy ? "Uploading…" : "Upload"}
      </button>
    </form>
  );
}
