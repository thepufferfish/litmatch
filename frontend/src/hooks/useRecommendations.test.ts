import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createElement, type ReactNode } from "react";
import { useRecommendations } from "./useRecommendations";
import api from "@/api/client";
import type { Mock } from "vitest";
import type { Book, RecommendationResponse } from "@/types";

// -- Mock API client ---------------------------------------------------------

vi.mock("@/api/client", () => ({
  default: {
    get: vi.fn(),
  },
}));

const mockGet = api.get as Mock;

// -- Test data ---------------------------------------------------------------

const mockBook: Book = {
  id: 1,
  title: "Test Book",
  author_id: 1,
  publisher_id: 1,
  publish_date: "2024-01-01",
  description: "A test book.",
  url: "https://example.com/test",
  cover: null,
  author: { id: 1, name: "Test Author" },
  publisher: { id: 1, name: "Test Publisher" },
  genres: [{ id: 1, name: "Fiction" }],
  avg_critic_rating: 3.0,
  review_count: 5,
};

const mockFictionResponse: RecommendationResponse = {
  items: [mockBook],
  meta: {
    strategy: "personalized",
    rating_count: 8,
    category: "fiction",
  },
};

const mockNonfictionResponse: RecommendationResponse = {
  items: [],
  meta: {
    strategy: "popular",
    rating_count: 2,
    category: "nonfiction",
  },
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

describe("useRecommendations", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("returns recommendation data for fiction category", async () => {
    mockGet.mockResolvedValue({ data: mockFictionResponse });

    const { result } = renderHook(
      () => useRecommendations({ category: "fiction" }),
      { wrapper: createWrapper() }
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toEqual(mockFictionResponse);
    expect(result.current.data?.meta.category).toBe("fiction");
    expect(result.current.data?.meta.strategy).toBe("personalized");
  });

  it("returns recommendation data for nonfiction category", async () => {
    mockGet.mockResolvedValue({ data: mockNonfictionResponse });

    const { result } = renderHook(
      () => useRecommendations({ category: "nonfiction" }),
      { wrapper: createWrapper() }
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toEqual(mockNonfictionResponse);
    expect(result.current.data?.meta.category).toBe("nonfiction");
  });

  it("passes category and limit params to API", async () => {
    mockGet.mockResolvedValue({ data: mockFictionResponse });

    const { result } = renderHook(
      () => useRecommendations({ category: "fiction", limit: 10 }),
      { wrapper: createWrapper() }
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockGet).toHaveBeenCalledWith("/recommendations/", {
      params: { category: "fiction", limit: 10 },
    });
  });

  it("uses default values when no params provided", async () => {
    mockGet.mockResolvedValue({ data: mockFictionResponse });

    const { result } = renderHook(
      () => useRecommendations(),
      { wrapper: createWrapper() }
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockGet).toHaveBeenCalledWith("/recommendations/", {
      params: { category: "all", limit: 20 },
    });
  });

  it("is disabled when enabled is false", () => {
    const { result } = renderHook(
      () => useRecommendations({ enabled: false }),
      { wrapper: createWrapper() }
    );

    expect(result.current.fetchStatus).toBe("idle");
    expect(mockGet).not.toHaveBeenCalled();
  });

  it("uses distinct queryKeys for different categories", async () => {
    mockGet.mockResolvedValue({ data: mockFictionResponse });

    const wrapper = createWrapper();

    const { result: fictionResult } = renderHook(
      () => useRecommendations({ category: "fiction" }),
      { wrapper }
    );

    await waitFor(() => expect(fictionResult.current.isSuccess).toBe(true));

    // Second call with different category should make a separate API call
    mockGet.mockResolvedValue({ data: mockNonfictionResponse });

    const { result: nonfictionResult } = renderHook(
      () => useRecommendations({ category: "nonfiction" }),
      { wrapper }
    );

    await waitFor(() => expect(nonfictionResult.current.isSuccess).toBe(true));

    // Two separate API calls should have been made
    expect(mockGet).toHaveBeenCalledTimes(2);
  });
});
