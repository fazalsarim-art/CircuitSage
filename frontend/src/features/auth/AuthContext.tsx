// Authentication state. The access token lives in module memory (see api/client); this
// context tracks the current user and drives the single-refresh flow. On mount it tries to
// restore a session from the HttpOnly refresh cookie.

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { apiJson, configureAuthHandlers, setAccessToken } from "../../api/client";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";

export interface User {
  id: string;
  email: string;
  role: string;
  daily_query_limit: number;
}

export type AuthStatus = "loading" | "authenticated" | "unauthenticated";

interface AuthValue {
  user: User | null;
  status: AuthStatus;
  isAdmin: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [status, setStatus] = useState<AuthStatus>("loading");
  const refreshPromise = useRef<Promise<boolean> | null>(null);

  const refresh = useCallback(async (): Promise<boolean> => {
    // Share a single in-flight refresh so concurrent 401s trigger only one call.
    if (refreshPromise.current) {
      return refreshPromise.current;
    }
    const promise = (async () => {
      try {
        const response = await fetch(`${BASE_URL}/auth/refresh`, {
          method: "POST",
          credentials: "include",
        });
        if (!response.ok) {
          return false;
        }
        const data = (await response.json()) as { access_token: string };
        setAccessToken(data.access_token);
        return true;
      } catch {
        return false;
      } finally {
        refreshPromise.current = null;
      }
    })();
    refreshPromise.current = promise;
    return promise;
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const data = await apiJson<{ access_token: string; user: User }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    setAccessToken(data.access_token);
    setUser(data.user);
    setStatus("authenticated");
  }, []);

  const clearSession = useCallback(() => {
    setAccessToken(null);
    setUser(null);
    setStatus("unauthenticated");
  }, []);

  const logout = useCallback(async () => {
    try {
      await fetch(`${BASE_URL}/auth/logout`, { method: "POST", credentials: "include" });
    } catch {
      // Ignore network errors on logout; clear local state regardless.
    }
    clearSession();
  }, [clearSession]);

  useEffect(() => {
    configureAuthHandlers({ refresh, onUnauthorized: clearSession });
  }, [refresh, clearSession]);

  useEffect(() => {
    let active = true;
    (async () => {
      const restored = await refresh();
      if (!active) return;
      if (!restored) {
        setStatus("unauthenticated");
        return;
      }
      try {
        const me = await apiJson<User>("/auth/me");
        if (active) {
          setUser(me);
          setStatus("authenticated");
        }
      } catch {
        if (active) setStatus("unauthenticated");
      }
    })();
    return () => {
      active = false;
    };
  }, [refresh]);

  const value = useMemo<AuthValue>(
    () => ({ user, status, isAdmin: user?.role === "admin", login, logout }),
    [user, status, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}
