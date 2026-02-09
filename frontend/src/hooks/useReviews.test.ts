import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createElement, type ReactNode } from "react";
import { useReviews } from "./useReviews";
import api from "@/api/client";
import type { Mock } from "vitest";
import type { Review } from "@/types";

// -- Mock API client ---------------------------------------------------------

vi.mock("@/api/client", () => ({
  default: {
    get: vi.fn(),
  },
}));

const mockGet = api.get as Mock;

// -- Test data ---------------------------------------------------------------

const mockReviews: Review[] = [
  {
    id: 1,
    book_id: 42,
    rating: 4,
    review: "Excellent book.",
    url: "https://example.com/review/1",
    critic: { id: 1, name: "Critic One" },
    publication: { id: 1, name: "Pub One" },
  },
  {
    id: 2,
    book_id: 42,
    rating: 2,
    review: "Disappointing.",
    url: "https://example.com/review/2",
    critic: { id: 2, name: "Critic Two" },
    publication: null,
  },
];

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

describe("useReviews", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("fetches reviews for a given book ID", async () => {
    mockGet.mockResolvedValue({ data: mockReviews });

    const { result } = renderHook(() => useReviews(42), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toEqual(mockReviews);
    expect(result.current.data).toHaveLength(2);
    expect(mockGet).toHaveBeenCalledWith("/reviews/42");
  });

  it("returns empty array when API returns no reviews", async () => {
    mockGet.mockResolvedValue({ data: [] });

    const { result } = renderHook(() => useReviews(42), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toEqual([]);
  });

  it("is disabled when bookId is 0 (falsy)", () => {
    const { result } = renderHook(() => useReviews(0), {
      wrapper: createWrapper(),
    });

    expect(result.current.fetchStatus).toBe("idle");
    expect(mockGet).not.toHaveBeenCalled();
  });

  it("reports error when the API call fails", async () => {
    mockGet.mockRejectedValue(new Error("Server error"));

    const { result } = renderHook(() => useReviews(42), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));

    expect(result.current.error?.message).toBe("Server error");
  });
});
