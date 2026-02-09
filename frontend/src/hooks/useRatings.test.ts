import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createElement, type ReactNode } from "react";
import { useUserRating, useSubmitRating } from "./useRatings";
import api from "@/api/client";
import type { Mock } from "vitest";
import type { UserRating } from "@/types";

// -- Mock API client ---------------------------------------------------------

vi.mock("@/api/client", () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

const mockGet = api.get as Mock;
const mockPost = api.post as Mock;

// -- Test data ---------------------------------------------------------------

const mockRating: UserRating = {
  id: 1,
  user_id: 10,
  book_id: 42,
  rating: 4,
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-01T00:00:00Z",
};

// -- Helpers -----------------------------------------------------------------

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return function Wrapper({ children }: { children: ReactNode }) {
    return createElement(QueryClientProvider, { client: queryClient }, children);
  };
}

// -- Tests: useUserRating ----------------------------------------------------

describe("useUserRating", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("fetches the user rating for a given book and user", async () => {
    mockGet.mockResolvedValue({ data: [mockRating] });

    const { result } = renderHook(() => useUserRating(42, 10), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toEqual(mockRating);
    expect(mockGet).toHaveBeenCalledWith("/ratings/", {
      params: { book_id: 42, user_id: 10 },
    });
  });

  it("returns null when the API returns an empty array", async () => {
    mockGet.mockResolvedValue({ data: [] });

    const { result } = renderHook(() => useUserRating(42, 10), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toBeNull();
  });

  it("is disabled when userId is undefined", () => {
    const { result } = renderHook(() => useUserRating(42, undefined), {
      wrapper: createWrapper(),
    });

    expect(result.current.fetchStatus).toBe("idle");
    expect(mockGet).not.toHaveBeenCalled();
  });

  it("is disabled when bookId is 0 (falsy)", () => {
    const { result } = renderHook(() => useUserRating(0, 10), {
      wrapper: createWrapper(),
    });

    expect(result.current.fetchStatus).toBe("idle");
    expect(mockGet).not.toHaveBeenCalled();
  });
});

// -- Tests: useSubmitRating --------------------------------------------------

describe("useSubmitRating", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("submits a rating via POST to /ratings/", async () => {
    const newRating: UserRating = {
      ...mockRating,
      rating: 5,
    };
    mockPost.mockResolvedValue({ data: newRating });

    const { result } = renderHook(() => useSubmitRating(), {
      wrapper: createWrapper(),
    });

    result.current.mutate({ book_id: 42, rating: 5 });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockPost).toHaveBeenCalledWith("/ratings/", {
      book_id: 42,
      rating: 5,
    });
    expect(result.current.data).toEqual(newRating);
  });

  it("reports error when the API call fails", async () => {
    mockPost.mockRejectedValue(new Error("Network error"));

    const { result } = renderHook(() => useSubmitRating(), {
      wrapper: createWrapper(),
    });

    result.current.mutate({ book_id: 42, rating: 3 });

    await waitFor(() => expect(result.current.isError).toBe(true));

    expect(result.current.error?.message).toBe("Network error");
  });
});
