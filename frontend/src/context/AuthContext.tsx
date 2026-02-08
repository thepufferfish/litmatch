import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import api from "@/api/client";
import { setAuthHelpers } from "@/api/client";
import type {
  AuthResponse,
  LoginCredentials,
  RegisterCredentials,
  UserPublic,
} from "@/types";

interface AuthContextValue {
  user: UserPublic | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (credentials: LoginCredentials) => Promise<void>;
  register: (credentials: RegisterCredentials) => Promise<void>;
  logout: () => Promise<void>;
  getAccessToken: () => string | null;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserPublic | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const accessTokenRef = useRef<string | null>(null);

  // Register auth helpers with the API client
  useEffect(() => {
    setAuthHelpers(
      () => accessTokenRef.current,
      (token: string | null) => {
        accessTokenRef.current = token;
      }
    );
  }, []);

  // Attempt silent refresh on mount
  useEffect(() => {
    const silentRefresh = async () => {
      try {
        const { data } = await api.post<AuthResponse>("/auth/refresh");
        accessTokenRef.current = data.access_token;
        setUser(data.user);
      } catch {
        // No valid refresh token - user is not authenticated
        accessTokenRef.current = null;
        setUser(null);
      } finally {
        setIsLoading(false);
      }
    };
    void silentRefresh();
  }, []);

  const login = useCallback(async (credentials: LoginCredentials) => {
    const { data } = await api.post<AuthResponse>("/auth/login", credentials);
    accessTokenRef.current = data.access_token;
    setUser(data.user);
  }, []);

  const register = useCallback(async (credentials: RegisterCredentials) => {
    const { data } = await api.post<AuthResponse>(
      "/auth/register",
      credentials
    );
    accessTokenRef.current = data.access_token;
    setUser(data.user);
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.post("/auth/logout");
    } finally {
      accessTokenRef.current = null;
      setUser(null);
    }
  }, []);

  const getAccessToken = useCallback(() => accessTokenRef.current, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: user !== null,
        isLoading,
        login,
        register,
        logout,
        getAccessToken,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
