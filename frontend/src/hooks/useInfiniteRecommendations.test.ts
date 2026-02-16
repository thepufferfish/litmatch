import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createElement, type ReactNode } from "react";
import { useInfiniteRecommendations } from "./useInfiniteRecommendations";
import api from "@/api/client";
import type { Mock } from "vitest";
import type { PaginatedRecommendationResponse } from "@/types";

// -- Mock API client ---------------------------------------------------------

vi.mock("@/api/client", () => ({
  default: {
    get: vi.fn(),
  },
}));

const mockGet = api.get as Mock;

// -- Test data ---------------------------------------------------------------

const mockPage1: PaginatedRecommendationResponse = {
  items: [
    {
      id: 1,
      title: "Book One",
      author_id: 1,
      publisher_id: 1,
      publish_date: "2024-01-01",
      description: "First book.",
      url: "https://example.com/1",
      cover: null,
      author: { id: 1, name: "Author One" },
      publisher: { id: 1, name: "Publisher" },
      genres: [{ id: 1, name: "Fiction" }],
      avg_critic_rating: 4.0,
      review_count: 10,
    },
  ],
  meta: {
    strategy: "popular",
    rating_count: 2,
    category: "fiction",
  },
  total: 40,
  offset: 0,
  limit: 20,
  has_more: true,
};

const mockPage2: PaginatedRecommendationResponse = {
  items: [
    {
      id: 2,
      title: "Book Two",
      author_id: 2,
      publisher_id: 2,
      publish_date: "2024-02-01",
      description: "Second book.",
      url: "https://example.com/2",
      cover: null,
      author: { id: 2, name: "Author Two" },
      publisher: { id: 2, name: "Publisher" },
      genres: [{ id: 2, name: "Mystery" }],
      avg_critic_rating: 3.5,
      review_count: 5,
    },
  ],
  meta: {
    strategy: "popular",
    rating_count: 2,
    category: "fiction",
  },
  total: 40,
  offset: 20,
  limit: 20,
  has_more: false,
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

describe("useInfiniteRecommendations", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("fetches the first page of recommendations", async () => {
    mockGet.mockResolvedValue({ data: mockPage1 });

    const { result } = renderHook(
      () => useInfiniteRecommendations({ category: "fiction" }),
      { wrapper: createWrapper() }
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data?.pages).toHaveLength(1);
    expect(result.current.data?.pages[0]).toEqual(mockPage1);
  });

  it("passes category and offset params to API", async () => {
    mockGet.mockResolvedValue({ data: mockPage1 });

    const { result } = renderHook(
      () => useInfiniteRecommendations({ category: "fiction" }),
      { wrapper: createWrapper() }
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockGet).toHaveBeenCalledWith("/recommendations/", {
      params: { category: "fiction", limit: 20, offset: 0 },
    });
  });

  it("passes genreId as genre_id param", async () => {
    mockGet.mockResolvedValue({ data: mockPage1 });

    const { result } = renderHook(
      () => useInfiniteRecommendations({ category: "fiction", genreId: 5 }),
      { wrapper: createWrapper() }
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockGet).toHaveBeenCalledWith("/recommendations/", {
      params: { category: "fiction", limit: 20, offset: 0, genre_id: 5 },
    });
  });

  it("reports hasNextPage when has_more is true", async () => {
    mockGet.mockResolvedValue({ data: mockPage1 });

    const { result } = renderHook(
      () => useInfiniteRecommendations({ category: "fiction" }),
      { wrapper: createWrapper() }
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.hasNextPage).toBe(true);
  });

  it("reports no next page when has_more is false", async () => {
    mockGet.mockResolvedValue({ data: mockPage2 });

    const { result } = renderHook(
      () => useInfiniteRecommendations({ category: "fiction" }),
      { wrapper: createWrapper() }
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.hasNextPage).toBe(false);
  });

  it("is disabled when enabled is false", () => {
    const { result } = renderHook(
      () => useInfiniteRecommendations({ enabled: false }),
      { wrapper: createWrapper() }
    );

    expect(result.current.fetchStatus).toBe("idle");
    expect(mockGet).not.toHaveBeenCalled();
  });

  it("uses distinct queryKeys for different categories", async () => {
    mockGet.mockResolvedValue({ data: mockPage1 });

    const wrapper = createWrapper();

    const { result: fictionResult } = renderHook(
      () => useInfiniteRecommendations({ category: "fiction" }),
      { wrapper }
    );

    await waitFor(() => expect(fictionResult.current.isSuccess).toBe(true));

    const { result: nonfictionResult } = renderHook(
      () => useInfiniteRecommendations({ category: "nonfiction" }),
      { wrapper }
    );

    await waitFor(() => expect(nonfictionResult.current.isSuccess).toBe(true));

    expect(mockGet).toHaveBeenCalledTimes(2);
  });

  it("uses distinct queryKeys for different genreIds", async () => {
    mockGet.mockResolvedValue({ data: mockPage1 });

    const wrapper = createWrapper();

    const { result: result1 } = renderHook(
      () => useInfiniteRecommendations({ category: "fiction", genreId: 1 }),
      { wrapper }
    );

    await waitFor(() => expect(result1.current.isSuccess).toBe(true));

    const { result: result2 } = renderHook(
      () => useInfiniteRecommendations({ category: "fiction", genreId: 2 }),
      { wrapper }
    );

    await waitFor(() => expect(result2.current.isSuccess).toBe(true));

    expect(mockGet).toHaveBeenCalledTimes(2);
  });
});
