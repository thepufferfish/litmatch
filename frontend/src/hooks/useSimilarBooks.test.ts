import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createElement, type ReactNode } from "react";
import { useSimilarBooks } from "./useSimilarBooks";
import api from "@/api/client";
import type { Mock } from "vitest";
import type { Book } from "@/types";

// -- Mock API client ---------------------------------------------------------

vi.mock("@/api/client", () => ({
  default: {
    get: vi.fn(),
  },
}));

const mockGet = api.get as Mock;

// -- Test data ---------------------------------------------------------------

const mockSimilarBooks: Book[] = [
  {
    id: 10,
    title: "Similar Book One",
    author_id: 1,
    publisher_id: 1,
    publish_date: "2024-03-01",
    description: "A similar book.",
    url: "https://example.com/book/10",
    cover: "https://example.com/cover10.jpg",
    author: { id: 1, name: "Author One" },
    publisher: { id: 1, name: "Publisher One" },
    genres: [{ id: 1, name: "Fiction" }],
    avg_critic_rating: 3.8,
    review_count: 5,
  },
  {
    id: 20,
    title: "Similar Book Two",
    author_id: 2,
    publisher_id: 2,
    publish_date: "2024-06-15",
    description: "Another similar book.",
    url: "https://example.com/book/20",
    cover: null,
    author: { id: 2, name: "Author Two" },
    publisher: null,
    genres: [],
    avg_critic_rating: null,
    review_count: 0,
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

describe("useSimilarBooks", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("fetches similar books for a given book ID", async () => {
    mockGet.mockResolvedValue({ data: mockSimilarBooks });

    const { result } = renderHook(() => useSimilarBooks(42), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toEqual(mockSimilarBooks);
    expect(result.current.data).toHaveLength(2);
    expect(mockGet).toHaveBeenCalledWith("/books/42/similar");
  });

  it("returns empty array when API returns no similar books", async () => {
    mockGet.mockResolvedValue({ data: [] });

    const { result } = renderHook(() => useSimilarBooks(42), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toEqual([]);
  });

  it("is disabled when bookId is 0 (falsy)", () => {
    const { result } = renderHook(() => useSimilarBooks(0), {
      wrapper: createWrapper(),
    });

    expect(result.current.fetchStatus).toBe("idle");
    expect(mockGet).not.toHaveBeenCalled();
  });

  it("is disabled when enabled parameter is false", () => {
    const { result } = renderHook(() => useSimilarBooks(42, false), {
      wrapper: createWrapper(),
    });

    expect(result.current.fetchStatus).toBe("idle");
    expect(mockGet).not.toHaveBeenCalled();
  });

  it("reports error when the API call fails", async () => {
    mockGet.mockRejectedValue(new Error("Server error"));

    const { result } = renderHook(() => useSimilarBooks(42), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));

    expect(result.current.error?.message).toBe("Server error");
  });

  it("has a 10-minute stale time", async () => {
    mockGet.mockResolvedValue({ data: mockSimilarBooks });

    const { result } = renderHook(() => useSimilarBooks(42), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.isStale).toBe(false);
  });
});
