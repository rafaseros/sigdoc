import { createContext, useContext, useState, useCallback, type ReactNode } from "react";
import { apiClient } from "./api-client";

interface User {
  id: string;
  email: string;
  role: string;
  tenant_id: string;
  email_verified: boolean;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string, fullName: string, organizationName: string) => Promise<void>;
  logout: () => void;
  isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(
    () => localStorage.getItem("access_token")
  );

  const login = useCallback(async (email: string, password: string) => {
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
  }, []);

  const signup = useCallback(async (email: string, password: string, fullName: string, organizationName: string) => {
    const { data } = await apiClient.post("/auth/signup", {
      email,
      password,
      full_name: fullName,
      organization_name: organizationName,
    });
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
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    setToken(null);
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, token, login, signup, logout, isAuthenticated: !!token }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider");
  return context;
}
