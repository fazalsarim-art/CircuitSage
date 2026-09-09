import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("../features/auth/AuthContext", () => ({ useAuth: () => ({ isAdmin: true }) }));

import { FeedbackPage } from "./FeedbackPage";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const feedback = {
  id: "f1",
  message_id: "m1",
  user_id: "u1",
  rating: 0,
  reason: "retrieval_miss",
  comment: "Missed CPOL.",
  status: "unresolved",
  reviewed_by: null,
  reviewed_at: null,
  resolution_note: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
  question: "Which register selects the SPI clock mode?",
  answer: "The CPOL/CPHA bits.",
  answer_status: "answered",
  retrieval_mode: "lexical",
  corrections: [],
};

function routeFetch(feedbackItems: unknown[], versions: unknown[]) {
  return vi.fn(async (url: string) => {
    const path = url.replace(/^.*\/api\/v1/, "");
    if (path.startsWith("/feedback")) return jsonResponse({ items: feedbackItems });
    if (path.startsWith("/benchmark/versions")) return jsonResponse({ items: versions });
    return jsonResponse({ items: [] });
  });
}

describe("FeedbackPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("lists feedback with rating, reason and question", async () => {
    vi.stubGlobal("fetch", routeFetch([feedback], []));

    render(<FeedbackPage />);

    expect(
      await screen.findByText("Which register selects the SPI clock mode?"),
    ).toBeInTheDocument();
    expect(screen.getByText("retrieval_miss")).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "👎" })).toBeInTheDocument();
  });

  it("shows an empty state when there is no feedback", async () => {
    vi.stubGlobal("fetch", routeFetch([], []));

    render(<FeedbackPage />);

    expect(await screen.findByText(/No feedback in this view/)).toBeInTheDocument();
  });
});
