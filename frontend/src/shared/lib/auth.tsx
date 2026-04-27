import { createContext, useContext, useState, useCallback, useEffect, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { apiClient } from "./api-client";

interface User {
  id: string;
  email: string;
  role: string;
  tenant_id: string;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(
    () => localStorage.getItem("access_token")
  );

  // Re-hydrate user when the page mounts/refreshes with an existing token.
  // Without this, every reload leaves user=null even though the token is in
  // localStorage — and every UI gate based on role/is_owner breaks until the
  // user logs out and back in.
  useEffect(() => {
    if (!token || user) return;
    let cancelled = false;
    apiClient
      .get("/auth/me")
      .then(({ data }) => {
        if (!cancelled) setUser(data);
      })
      .catch(() => {
        // Token is invalid/expired — clear stale credentials so the
        // protected routes redirect to /login cleanly.
        if (cancelled) return;
        localStorage.removeItem("access_token");
        localStorage.removeItem("refresh_token");
        setToken(null);
      });
    return () => {
      cancelled = true;
    };
  }, [token, user]);

  const login = useCallback(async (email: string, password: string) => {
    // Wipe any cached queries from a prior session BEFORE the new token is
    // installed. Otherwise queries keyed solely by URL/filters (templates,
    // documents, shares) would return the previous user's data on first read.
    queryClient.clear();

    const { data } = await apiClient.post("/auth/login", { email, password });
    localStorage.setItem("access_token", data.access_token);
    if (data.refresh_token) {
      localStorage.setItem("refresh_token", data.refresh_token);
    }
    setToken(data.access_token);

    try {
      const { data: userData } = await apiClient.get("/auth/me");
      setUser(userData);
    } catch {
      // Token is valid but /auth/me failed — let user proceed without profile data
    }
  }, [queryClient]);

  const logout = useCallback(() => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    setToken(null);
    setUser(null);
    // Drop every cached query — prevents the previous user's templates,
    // documents, shares, audit, and /auth/me data from leaking into the
    // next session in the same browser tab.
    queryClient.clear();
  }, [queryClient]);

  return (
    <AuthContext.Provider value={{ user, token, login, logout, isAuthenticated: !!token }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider");
  return context;
}
