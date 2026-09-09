import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("../features/auth/AuthContext", () => ({ useAuth: () => ({ isAdmin: true }) }));

import { DocumentsPage } from "./DocumentsPage";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("DocumentsPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("lists documents and shows the admin upload form", async () => {
    const doc = {
      id: "d1",
      title: "UART Manual",
      status: "indexed",
      visibility: "shared",
      page_count: 3,
      chunk_count: 2,
      source_url: null,
      publisher: null,
      created_at: "",
      updated_at: "",
    };
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse({ items: [doc], next_cursor: null })),
    );

    render(<DocumentsPage />);

    expect(await screen.findByText("UART Manual")).toBeInTheDocument();
    expect(screen.getByText("Upload a PDF")).toBeInTheDocument();
    expect(screen.getByText("indexed")).toBeInTheDocument();
  });

  it("shows an empty state when there are no documents", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse({ items: [], next_cursor: null })),
    );

    render(<DocumentsPage />);

    expect(await screen.findByText(/No documents yet/)).toBeInTheDocument();
  });
});
