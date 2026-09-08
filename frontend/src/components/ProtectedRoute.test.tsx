import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

vi.mock("../features/auth/AuthContext", () => ({ useAuth: vi.fn() }));

import { useAuth } from "../features/auth/AuthContext";
import { ProtectedRoute } from "./ProtectedRoute";

function renderProtected(status: string) {
  vi.mocked(useAuth).mockReturnValue({ status } as unknown as ReturnType<typeof useAuth>);
  return render(
    <MemoryRouter initialEntries={["/secret"]}>
      <Routes>
        <Route element={<ProtectedRoute />}>
          <Route path="/secret" element={<div>secret content</div>} />
        </Route>
        <Route path="/signin" element={<div>sign in page</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("ProtectedRoute", () => {
  it("shows a loading state while auth resolves", () => {
    renderProtected("loading");
    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("redirects unauthenticated users to sign in", () => {
    renderProtected("unauthenticated");
    expect(screen.getByText("sign in page")).toBeInTheDocument();
  });

  it("renders protected content when authenticated", () => {
    renderProtected("authenticated");
    expect(screen.getByText("secret content")).toBeInTheDocument();
  });
});
