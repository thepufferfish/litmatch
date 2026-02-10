import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createElement, type ReactNode } from "react";
import { useUserProfile } from "./useUserProfile";
import api from "@/api/client";
import type { Mock } from "vitest";
import type { UserProfile } from "@/types";

// -- Mock API client ---------------------------------------------------------

vi.mock("@/api/client", () => ({
  default: {
    get: vi.fn(),
  },
}));

const mockGet = api.get as Mock;

// -- Test data ---------------------------------------------------------------

const mockProfile: UserProfile = {
  id: 10,
  username: "reader",
  rating_count: 7,
};

// -- Helpers -----------------------------------------------------------------

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });

  return function Wrapper({ children }: { children: ReactNode }) {
    return createElement(QueryClientProvider, { client: queryClient }, children);
  };
}

// -- Tests -------------------------------------------------------------------

describe("useUserProfile", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("fetches profile data from /users/me", async () => {
    mockGet.mockResolvedValue({ data: mockProfile });

    const { result } = renderHook(() => useUserProfile(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toEqual(mockProfile);
    expect(mockGet).toHaveBeenCalledWith("/users/me");
  });

  it("returns profile with id, username, and rating_count", async () => {
    mockGet.mockResolvedValue({ data: mockProfile });

    const { result } = renderHook(() => useUserProfile(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data?.id).toBe(10);
    expect(result.current.data?.username).toBe("reader");
    expect(result.current.data?.rating_count).toBe(7);
  });

  it("is disabled when enabled is false", () => {
    const { result } = renderHook(() => useUserProfile(false), {
      wrapper: createWrapper(),
    });

    expect(result.current.fetchStatus).toBe("idle");
    expect(mockGet).not.toHaveBeenCalled();
  });
});
