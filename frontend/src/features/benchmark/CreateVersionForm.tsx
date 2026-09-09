import { useState, type FormEvent } from "react";

import type { ApiError } from "../../api/client";
import { createVersion } from "./api";

export function CreateVersionForm({ onCreated }: { onCreated: () => void }) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!name.trim()) {
      setError("A benchmark name is required.");
      return;
    }
    setError(null);
    setBusy(true);
    try {
      await createVersion({ name: name.trim(), description: description.trim() || undefined });
      setName("");
      setDescription("");
      onCreated();
    } catch (err) {
      setError((err as ApiError)?.message ?? "Could not create version.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="doc-upload" onSubmit={handleSubmit} aria-label="Create benchmark version">
      <h2>New benchmark version</h2>
      <label htmlFor="bench-name">Name</label>
      <input
        id="bench-name"
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="circuitsage"
      />
      <label htmlFor="bench-desc">Description (optional)</label>
      <input id="bench-desc" value={description} onChange={(e) => setDescription(e.target.value)} />
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      <button type="submit" disabled={busy}>
        {busy ? "Creating…" : "Create version"}
      </button>
    </form>
  );
}
