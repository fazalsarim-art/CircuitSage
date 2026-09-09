import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AskPage } from "./AskPage";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function renderAsk() {
  return render(
    <MemoryRouter>
      <AskPage />
    </MemoryRouter>,
  );
}

describe("AskPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("sends a question and renders the grounded answer with a source", async () => {
    const chat = {
      user_message: {
        id: "m1",
        role: "user",
        content: "why?",
        answer_status: null,
        retrieval_mode: null,
        created_at: "",
      },
      assistant_message: {
        id: "m2",
        role: "assistant",
        content: "It clears on read [C1].",
        answer_status: "answered",
        retrieval_mode: "hybrid",
        created_at: "",
      },
      answer_status: "answered",
      sources: [
        {
          label: "C1",
          chunk_id: "ch1",
          document_id: "d1",
          document_title: "UART Manual",
          page_start: 1,
          page_end: 2,
          preview: "the overrun flag clears on read",
        },
      ],
      timings_ms: { total: 12 },
    };
    const fetchMock = vi.fn(async (url: string | URL, init?: RequestInit) => {
      const target = String(url);
      const method = init?.method ?? "GET";
      if (target.endsWith("/conversations") && method === "GET") {
        return jsonResponse({ items: [], next_cursor: null });
      }
      if (target.endsWith("/conversations") && method === "POST") {
        return jsonResponse({ id: "c1", title: "t", created_at: "", updated_at: "" });
      }
      if (target.includes("/messages")) {
        return jsonResponse(chat);
      }
      return jsonResponse({}, 404);
    });
    vi.stubGlobal("fetch", fetchMock);

    renderAsk();
    await userEvent.type(screen.getByLabelText("Question"), "why does the flag stay set?");
    await userEvent.click(screen.getByRole("button", { name: "Ask" }));

    expect(await screen.findByText("It clears on read [C1].")).toBeInTheDocument();
    expect(screen.getByText(/UART Manual/)).toBeInTheDocument();
    expect(screen.getByText("Answered")).toBeInTheDocument();
  });

  it("shows corpus-not-ready guidance when there is no indexed corpus", async () => {
    const fetchMock = vi.fn(async (url: string | URL, init?: RequestInit) => {
      const target = String(url);
      const method = init?.method ?? "GET";
      if (target.endsWith("/conversations") && method === "GET") {
        return jsonResponse({ items: [], next_cursor: null });
      }
      if (target.endsWith("/conversations") && method === "POST") {
        return jsonResponse({ id: "c1", title: "t", created_at: "", updated_at: "" });
      }
      if (target.includes("/messages")) {
        return jsonResponse({ error: { code: "corpus_not_ready", message: "no docs" } }, 409);
      }
      return jsonResponse({}, 404);
    });
    vi.stubGlobal("fetch", fetchMock);

    renderAsk();
    await userEvent.type(screen.getByLabelText("Question"), "why does the flag stay set?");
    await userEvent.click(screen.getByRole("button", { name: "Ask" }));

    expect(await screen.findByText(/No indexed documents yet/)).toBeInTheDocument();
  });
});
