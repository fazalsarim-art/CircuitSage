import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AuthProvider } from "./AuthContext";
import { SignInPage } from "./SignInPage";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function renderSignIn() {
  return render(
    <MemoryRouter initialEntries={["/signin"]}>
      <AuthProvider>
        <Routes>
          <Route path="/signin" element={<SignInPage />} />
          <Route path="/" element={<div>home page</div>} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("SignInPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("signs in and navigates home", async () => {
    const fetchMock = vi.fn(async (url: string | URL) => {
      const target = String(url);
      if (target.endsWith("/auth/refresh")) return jsonResponse({}, 401);
      if (target.endsWith("/auth/login")) {
        return jsonResponse({
          access_token: "tok",
          user: { id: "1", email: "a@b.com", role: "member", daily_query_limit: 1000 },
        });
      }
      return jsonResponse({}, 404);
    });
    vi.stubGlobal("fetch", fetchMock);

    renderSignIn();
    await userEvent.type(screen.getByLabelText("Email"), "a@b.com");
    await userEvent.type(screen.getByLabelText("Password"), "password12345");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => expect(screen.getByText("home page")).toBeInTheDocument());
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/auth/login"),
      expect.anything(),
    );
  });

  it("shows an error message on invalid credentials", async () => {
    const fetchMock = vi.fn(async (url: string | URL) => {
      const target = String(url);
      if (target.endsWith("/auth/refresh")) return jsonResponse({}, 401);
      if (target.endsWith("/auth/login")) {
        return jsonResponse({ error: { code: "invalid_credentials", message: "bad" } }, 401);
      }
      return jsonResponse({}, 404);
    });
    vi.stubGlobal("fetch", fetchMock);

    renderSignIn();
    await userEvent.type(screen.getByLabelText("Email"), "a@b.com");
    await userEvent.type(screen.getByLabelText("Password"), "wrongpassword");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/incorrect/i));
  });
});
