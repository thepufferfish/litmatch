import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AuthProvider, useAuth } from "./AuthContext";
import api from "@/api/client";
import type { Mock } from "vitest";
import type { AuthResponse } from "@/types";

// -- Mock API client ---------------------------------------------------------

vi.mock("@/api/client", () => {
  const mockPost = vi.fn();
  return {
    default: {
      post: mockPost,
      interceptors: {
        request: { use: vi.fn() },
        response: { use: vi.fn() },
      },
      defaults: {
        baseURL: "/api",
        withCredentials: true,
        headers: { "Content-Type": "application/json" },
      },
    },
    setAuthHelpers: vi.fn(),
  };
});

const mockPost = api.post as Mock;

// -- Test helpers ------------------------------------------------------------

const mockAuthResponse: AuthResponse = {
  access_token: "test-access-token",
  token_type: "bearer",
  user: { id: 1, username: "testuser" },
};

/**
 * Test component that consumes the auth context and exposes its state
 * through rendered text so we can assert on it.
 */
function AuthConsumer() {
  const { user, isAuthenticated, isLoading, login, register, logout, getAccessToken } = useAuth();

  return (
    <div>
      <span data-testid="loading">{String(isLoading)}</span>
      <span data-testid="authenticated">{String(isAuthenticated)}</span>
      <span data-testid="username">{user?.username ?? "none"}</span>
      <span data-testid="token">{getAccessToken() ?? "none"}</span>
      <button
        data-testid="login-btn"
        onClick={() => login({ username: "testuser", password: "pass123" })}
      >
        Login
      </button>
      <button
        data-testid="register-btn"
        onClick={() => register({ username: "newuser", password: "pass456" })}
      >
        Register
      </button>
      <button data-testid="logout-btn" onClick={() => void logout()}>
        Logout
      </button>
    </div>
  );
}

function renderWithAuth() {
  return render(
    <AuthProvider>
      <AuthConsumer />
    </AuthProvider>
  );
}

// -- Tests -------------------------------------------------------------------

describe("AuthContext", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("silent refresh on mount", () => {
    it("sets user when silent refresh succeeds", async () => {
      mockPost.mockResolvedValue({ data: mockAuthResponse });

      renderWithAuth();

      // Initially loading
      expect(screen.getByTestId("loading").textContent).toBe("true");

      // After refresh completes
      await waitFor(() => {
        expect(screen.getByTestId("loading").textContent).toBe("false");
      });

      expect(screen.getByTestId("authenticated").textContent).toBe("true");
      expect(screen.getByTestId("username").textContent).toBe("testuser");
    });

    it("handles 404 from silent refresh gracefully (no crash, no user)", async () => {
      // This is the exact scenario from the bug report: the refresh endpoint
      // returns 404 when no user is logged in. The AuthProvider must catch
      // this error, set isLoading=false, and leave user as null.
      const error = new Error("Request failed with status code 404");
      (error as { response?: { status: number } }).response = { status: 404 };
      mockPost.mockRejectedValue(error);

      renderWithAuth();

      await waitFor(() => {
        expect(screen.getByTestId("loading").textContent).toBe("false");
      });

      expect(screen.getByTestId("authenticated").textContent).toBe("false");
      expect(screen.getByTestId("username").textContent).toBe("none");
    });

    it("handles 401 from silent refresh gracefully", async () => {
      const error = new Error("Request failed with status code 401");
      (error as { response?: { status: number } }).response = { status: 401 };
      mockPost.mockRejectedValue(error);

      renderWithAuth();

      await waitFor(() => {
        expect(screen.getByTestId("loading").textContent).toBe("false");
      });

      expect(screen.getByTestId("authenticated").textContent).toBe("false");
      expect(screen.getByTestId("username").textContent).toBe("none");
    });

    it("handles network error from silent refresh gracefully", async () => {
      mockPost.mockRejectedValue(new Error("Network Error"));

      renderWithAuth();

      await waitFor(() => {
        expect(screen.getByTestId("loading").textContent).toBe("false");
      });

      expect(screen.getByTestId("authenticated").textContent).toBe("false");
    });
  });

  describe("login", () => {
    it("sets user and token after successful login", async () => {
      // Silent refresh fails (no prior session)
      mockPost.mockRejectedValueOnce(new Error("No session"));
      // Login succeeds
      mockPost.mockResolvedValueOnce({ data: mockAuthResponse });

      const user = userEvent.setup();
      renderWithAuth();

      // Wait for silent refresh to complete
      await waitFor(() => {
        expect(screen.getByTestId("loading").textContent).toBe("false");
      });

      expect(screen.getByTestId("authenticated").textContent).toBe("false");

      // Click login
      await user.click(screen.getByTestId("login-btn"));

      await waitFor(() => {
        expect(screen.getByTestId("authenticated").textContent).toBe("true");
      });
      expect(screen.getByTestId("username").textContent).toBe("testuser");
    });
  });

  describe("logout", () => {
    it("clears user after logout", async () => {
      // Silent refresh succeeds (user is logged in)
      mockPost.mockResolvedValueOnce({ data: mockAuthResponse });
      // Logout succeeds
      mockPost.mockResolvedValueOnce({});

      const user = userEvent.setup();
      renderWithAuth();

      // Wait for authenticated state
      await waitFor(() => {
        expect(screen.getByTestId("authenticated").textContent).toBe("true");
      });

      // Click logout
      await user.click(screen.getByTestId("logout-btn"));

      await waitFor(() => {
        expect(screen.getByTestId("authenticated").textContent).toBe("false");
      });
      expect(screen.getByTestId("username").textContent).toBe("none");
    });

    it("clears user even when logout API call fails", async () => {
      // Silent refresh succeeds
      mockPost.mockResolvedValueOnce({ data: mockAuthResponse });
      // Logout fails (server error)
      mockPost.mockRejectedValueOnce(new Error("Server error"));

      const user = userEvent.setup();
      renderWithAuth();

      await waitFor(() => {
        expect(screen.getByTestId("authenticated").textContent).toBe("true");
      });

      await user.click(screen.getByTestId("logout-btn"));

      await waitFor(() => {
        expect(screen.getByTestId("authenticated").textContent).toBe("false");
      });
    });
  });

  describe("register", () => {
    it("sets user and token after successful registration", async () => {
      // Silent refresh fails (no prior session)
      mockPost.mockRejectedValueOnce(new Error("No session"));
      // Register succeeds
      const registerResponse: AuthResponse = {
        access_token: "new-user-token",
        token_type: "bearer",
        user: { id: 2, username: "newuser" },
      };
      mockPost.mockResolvedValueOnce({ data: registerResponse });

      const user = userEvent.setup();
      renderWithAuth();

      await waitFor(() => {
        expect(screen.getByTestId("loading").textContent).toBe("false");
      });

      await user.click(screen.getByTestId("register-btn"));

      await waitFor(() => {
        expect(screen.getByTestId("authenticated").textContent).toBe("true");
      });
      expect(screen.getByTestId("username").textContent).toBe("newuser");
    });
  });

  describe("getAccessToken", () => {
    it("returns null when no user is logged in", async () => {
      mockPost.mockRejectedValueOnce(new Error("No session"));

      renderWithAuth();

      await waitFor(() => {
        expect(screen.getByTestId("loading").textContent).toBe("false");
      });

      expect(screen.getByTestId("token").textContent).toBe("none");
    });
  });

  describe("useAuth outside provider", () => {
    it("throws when used outside AuthProvider", () => {
      // Suppress console.error for the expected error
      const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

      expect(() => {
        render(<AuthConsumer />);
      }).toThrow("useAuth must be used within an AuthProvider");

      consoleSpy.mockRestore();
    });
  });
});
