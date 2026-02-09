import axios, { type InternalAxiosRequestConfig } from "axios";
import toast from "react-hot-toast";

type TokenGetter = () => string | null;
type TokenSetter = (token: string | null) => void;

let getToken: TokenGetter = () => null;
let setToken: TokenSetter = () => {};
let refreshPromise: Promise<string | null> | null = null;

/**
 * Register auth helper functions from AuthContext.
 * This allows the API client to access and update the in-memory access token.
 */
export function setAuthHelpers(getter: TokenGetter, setter: TokenSetter): void {
  getToken = getter;
  setToken = setter;
}

const api = axios.create({
  baseURL: "/api",
  withCredentials: true,
  headers: {
    "Content-Type": "application/json",
  },
});

// Request interceptor: inject Authorization header
api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = getToken();
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

async function attemptTokenRefresh(): Promise<string | null> {
  try {
    // Use the configured api instance (not bare axios) so the request goes
    // through the correct baseURL ("/api") and Vite proxy configuration.
    // Bare axios.post("/api/auth/refresh") bypasses proxy rewriting in
    // production, resulting in a 404.
    const { data } = await api.post<{ access_token: string }>(
      "/auth/refresh",
      {}
    );
    const newToken = data.access_token;
    setToken(newToken);
    return newToken;
  } catch {
    setToken(null);
    return null;
  }
}

// Response interceptor: handle errors and 401 refresh logic
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (!error.response) {
      toast.error("Cannot connect to server. Please try again.");
      return Promise.reject(error);
    }

    const { status, data, config: originalConfig } = error.response as {
      status: number;
      data: { detail?: string | unknown[] };
      config: InternalAxiosRequestConfig & { _retry?: boolean };
    };

    // 401 refresh logic (skip for auth endpoints to avoid loops)
    if (
      status === 401 &&
      !originalConfig._retry &&
      !originalConfig.url?.includes("/auth/")
    ) {
      originalConfig._retry = true;

      // Use a shared promise so concurrent 401s don't trigger multiple refreshes
      if (!refreshPromise) {
        refreshPromise = attemptTokenRefresh().finally(() => {
          refreshPromise = null;
        });
      }

      const newToken = await refreshPromise;
      if (newToken) {
        originalConfig.headers.Authorization = `Bearer ${newToken}`;
        return api(originalConfig);
      }

      // Refresh failed - don't show toast for auth failures
      return Promise.reject(error);
    }

    if (status === 429) {
      toast.error("Too many requests. Please wait a moment and try again.");
    } else if (status === 500) {
      toast.error("Something went wrong. Please try again later.");
    } else if (data?.detail) {
      if (typeof data.detail === "string") {
        toast.error(data.detail);
      } else if (Array.isArray(data.detail)) {
        toast.error("Invalid request. Please check your input.");
      }
    }

    return Promise.reject(error);
  }
);

export default api;
