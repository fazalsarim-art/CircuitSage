import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("../features/auth/AuthContext", () => ({ useAuth: () => ({ isAdmin: true }) }));

import { BenchmarkPage } from "./BenchmarkPage";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const version = {
  id: "v1",
  name: "circuitsage",
  version: 1,
  status: "draft",
  description: null,
  published_at: null,
  source_commit: null,
  created_at: "2026-01-01T00:00:00Z",
  case_count: 3,
};

function routeFetch(routes: Record<string, unknown>) {
  return vi.fn(async (url: string) => {
    const path = url.replace(/^.*\/api\/v1/, "");
    for (const [prefix, body] of Object.entries(routes)) {
      if (path.startsWith(prefix)) return jsonResponse(body);
    }
    return jsonResponse({ items: [] });
  });
}

describe("BenchmarkPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("lists versions and shows the admin create form", async () => {
    vi.stubGlobal("fetch", routeFetch({ "/benchmark/versions": { items: [version] } }));

    render(<BenchmarkPage />);

    expect(await screen.findByText("circuitsage")).toBeInTheDocument();
    expect(screen.getByText("New benchmark version")).toBeInTheDocument();
    expect(screen.getByText("draft")).toBeInTheDocument();
  });

  it("shows an empty state when there are no versions", async () => {
    vi.stubGlobal("fetch", routeFetch({ "/benchmark/versions": { items: [] } }));

    render(<BenchmarkPage />);

    expect(await screen.findByText(/No benchmark versions yet/)).toBeInTheDocument();
  });
});
