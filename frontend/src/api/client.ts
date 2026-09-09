// Typed fetch wrapper: attaches the in-memory access token, performs a single refresh on
// 401 (via a handler set by the auth context), and never loops. The access token is held
// in module memory only — never localStorage.

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";

let accessToken: string | null = null;
let refreshHandler: (() => Promise<boolean>) | null = null;
let unauthorizedHandler: (() => void) | null = null;

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

export function configureAuthHandlers(handlers: {
  refresh: () => Promise<boolean>;
  onUnauthorized: () => void;
}): void {
  refreshHandler = handlers.refresh;
  unauthorizedHandler = handlers.onUnauthorized;
}

export interface ApiError {
  status: number;
  code: string;
  message: string;
}

async function parseError(response: Response): Promise<ApiError> {
  let code = "error";
  let message = response.statusText || "Request failed";
  try {
    const body = await response.json();
    if (body?.error) {
      code = body.error.code ?? code;
      message = body.error.message ?? message;
    }
  } catch {
    // Non-JSON error body — keep defaults.
  }
  return { status: response.status, code, message };
}

export async function apiFetch(
  path: string,
  options: RequestInit = {},
  retried = false,
): Promise<Response> {
  const headers = new Headers(options.headers);
  if (accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }
  // Only set JSON content-type for string bodies; let the browser set the multipart
  // boundary for FormData uploads.
  if (typeof options.body === "string" && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers,
    credentials: "include",
  });

  if (response.status === 401 && !retried && refreshHandler) {
    const refreshed = await refreshHandler();
    if (refreshed) {
      return apiFetch(path, options, true);
    }
    unauthorizedHandler?.();
  }
  return response;
}

export async function apiJson<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await apiFetch(path, options);
  if (!response.ok) {
    throw await parseError(response);
  }
  return (await response.json()) as T;
}
