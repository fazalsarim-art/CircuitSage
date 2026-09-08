import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { apiFetch, configureAuthHandlers, setAccessToken } from "./client";

describe("apiFetch", () => {
  beforeEach(() => {
    setAccessToken(null);
    configureAuthHandlers({ refresh: async () => false, onUnauthorized: () => {} });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("attaches the bearer token and includes credentials", async () => {
    setAccessToken("tok123");
    const fetchMock = vi.fn().mockResolvedValue(new Response("{}", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await apiFetch("/health");

    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect(new Headers(init.headers).get("Authorization")).toBe("Bearer tok123");
    expect(init.credentials).toBe("include");
  });

  it("refreshes once on 401 then retries the request", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response("{}", { status: 401 }))
      .mockResolvedValueOnce(new Response("{}", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const refresh = vi.fn().mockResolvedValue(true);
    configureAuthHandlers({ refresh, onUnauthorized: () => {} });

    const response = await apiFetch("/thing");

    expect(refresh).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(response.status).toBe(200);
  });

  it("does not loop when refresh fails and signals unauthorized", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("{}", { status: 401 }));
    vi.stubGlobal("fetch", fetchMock);
    const refresh = vi.fn().mockResolvedValue(false);
    const onUnauthorized = vi.fn();
    configureAuthHandlers({ refresh, onUnauthorized });

    const response = await apiFetch("/thing");

    expect(refresh).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(onUnauthorized).toHaveBeenCalledTimes(1);
    expect(response.status).toBe(401);
  });
});
