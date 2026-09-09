import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("../features/auth/AuthContext", () => ({ useAuth: () => ({ isAdmin: true }) }));

import { EvalRunsPage } from "./EvalRunsPage";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const publishedVersion = {
  id: "v1",
  name: "circuitsage",
  version: 1,
  status: "published",
  description: null,
  published_at: "2026-01-02T00:00:00Z",
  source_commit: null,
  created_at: "2026-01-01T00:00:00Z",
  case_count: 100,
};

const run = {
  id: "r1",
  benchmark_version_id: "v1",
  status: "succeeded",
  retrieval_mode: "hybrid",
  top_k: 10,
  candidate_k: 30,
  rrf_k: 60,
  reranker_model: null,
  embedding_model: "text-embedding-3-small",
  corpus_fingerprint: "abc123def456",
  metrics: { hit_at_5: 1.0, mrr_at_10: 0.83, ndcg_at_10: 0.91 },
  error_code: null,
  created_at: "2026-01-03T00:00:00Z",
  started_at: "2026-01-03T00:00:01Z",
  finished_at: "2026-01-03T00:00:05Z",
};

function routeFetch(runs: unknown[], versions: unknown[]) {
  return vi.fn(async (url: string) => {
    const path = url.replace(/^.*\/api\/v1/, "");
    if (path.startsWith("/evals/runs")) return jsonResponse({ items: runs });
    if (path.startsWith("/benchmark/versions")) return jsonResponse({ items: versions });
    return jsonResponse({ items: [] });
  });
}

describe("EvalRunsPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("lists runs and offers a published version to evaluate", async () => {
    vi.stubGlobal("fetch", routeFetch([run], [publishedVersion]));

    render(<EvalRunsPage />);

    // 0.910 (nDCG@10) is unique to the run row; "hybrid" also appears in the mode select.
    expect(await screen.findByText("0.910")).toBeInTheDocument();
    expect(screen.getByText("Queue an evaluation run")).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "hybrid" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: /circuitsage v1/ })).toBeInTheDocument();
  });

  it("shows an empty state when there are no runs", async () => {
    vi.stubGlobal("fetch", routeFetch([], [publishedVersion]));

    render(<EvalRunsPage />);

    expect(await screen.findByText(/No evaluation runs yet/)).toBeInTheDocument();
  });
});
