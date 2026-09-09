import { useState, type FormEvent } from "react";

import { RETRIEVAL_MODES } from "./types";

export interface ComposerSubmit {
  content: string;
  retrieval_mode: string;
  top_k: number;
  reranker_enabled: boolean;
}

export function QueryComposer({
  disabled,
  onSubmit,
}: {
  disabled: boolean;
  onSubmit: (value: ComposerSubmit) => void;
}) {
  const [content, setContent] = useState("");
  const [mode, setMode] = useState("hybrid");
  const [topK, setTopK] = useState(8);
  const [rerank, setRerank] = useState(false);

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const trimmed = content.trim();
    if (trimmed.length < 3) return;
    onSubmit({ content: trimmed, retrieval_mode: mode, top_k: topK, reranker_enabled: rerank });
    setContent("");
  }

  return (
    <form className="composer" onSubmit={handleSubmit} aria-label="Ask a question">
      <label htmlFor="question" className="sr-only">
        Question
      </label>
      <textarea
        id="question"
        rows={3}
        value={content}
        disabled={disabled}
        placeholder="Ask a debugging question, e.g. why does the SPI status register stay busy?"
        onChange={(e) => setContent(e.target.value)}
      />
      <div className="composer-controls">
        <label htmlFor="mode">Retriever</label>
        <select id="mode" value={mode} onChange={(e) => setMode(e.target.value)}>
          {RETRIEVAL_MODES.map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>

        <label htmlFor="topk">Top k</label>
        <input
          id="topk"
          type="number"
          min={1}
          max={20}
          value={topK}
          onChange={(e) => setTopK(Number(e.target.value))}
        />

        <label htmlFor="rerank" className="checkbox">
          <input
            id="rerank"
            type="checkbox"
            checked={rerank}
            onChange={(e) => setRerank(e.target.checked)}
          />
          Reranker
        </label>

        <button type="submit" disabled={disabled || content.trim().length < 3}>
          {disabled ? "Thinking…" : "Ask"}
        </button>
      </div>
    </form>
  );
}
