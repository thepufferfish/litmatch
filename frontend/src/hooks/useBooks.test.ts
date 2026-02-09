import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createElement, type ReactNode } from "react";
import { useBooks, useSearchBooks } from "./useBooks";
import api from "@/api/client";
import type { Mock } from "vitest";
import type { Book, PaginatedResponse } from "@/types";

// ── Mock API client ─────────────────────────────────────────────────

vi.mock("@/api/client", () => ({
  default: {
    get: vi.fn(),
  },
}));

const mockGet = api.get as Mock;

// ── Test data ───────────────────────────────────────────────────────

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

const validResponse: PaginatedResponse<Book> = {
  items: [mockBook],
  total: 1,
  page: 1,
  limit: 24,
};

// ── Helpers ─────────────────────────────────────────────────────────

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  return function Wrapper({ children }: { children: ReactNode }) {
    return createElement(QueryClientProvider, { client: queryClient }, children);
  };
}

// ── Tests ───────────────────────────────────────────────────────────

describe("useBooks", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("returns valid paginated data for a well-formed response", async () => {
    mockGet.mockResolvedValue({ data: validResponse });

    const { result } = renderHook(() => useBooks({ page: 1 }), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toEqual(validResponse);
    expect(result.current.data?.total).toBe(1);
    expect(result.current.data?.limit).toBe(24);
    expect(result.current.data?.items).toHaveLength(1);
  });

  it("normalizes missing total to 0", async () => {
    // API returns response without 'total' field
    const malformed = { items: [mockBook], page: 1, limit: 24 };
    mockGet.mockResolvedValue({ data: malformed });

    const { result } = renderHook(() => useBooks({ page: 1 }), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    // After validation, total should be normalized to 0
    expect(result.current.data?.total).toBe(0);
  });

  it("normalizes missing limit to the requested limit", async () => {
    // API returns response without 'limit' field
    const malformed = { items: [mockBook], total: 1, page: 1 };
    mockGet.mockResolvedValue({ data: malformed });

    const { result } = renderHook(() => useBooks({ page: 1, limit: 24 }), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    // After validation, limit should be normalized to the requested limit
    expect(result.current.data?.limit).toBe(24);
  });

  it("normalizes missing items to empty array", async () => {
    // API returns response without 'items' field
    const malformed = { total: 0, page: 1, limit: 24 };
    mockGet.mockResolvedValue({ data: malformed });

    const { result } = renderHook(() => useBooks({ page: 1 }), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    // After validation, items should be normalized to empty array
    expect(result.current.data?.items).toEqual([]);
  });

  it("normalizes limit of 0 to the requested limit", async () => {
    // API returns limit: 0 which would cause division by zero
    const malformed = { items: [mockBook], total: 1, page: 1, limit: 0 };
    mockGet.mockResolvedValue({ data: malformed });

    const { result } = renderHook(() => useBooks({ page: 1, limit: 24 }), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data?.limit).toBe(24);
  });

  it("passes page and limit params to API", async () => {
    mockGet.mockResolvedValue({ data: validResponse });

    const { result } = renderHook(() => useBooks({ page: 3, limit: 12 }), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockGet).toHaveBeenCalledWith("/books/", {
      params: { page: 3, limit: 12 },
    });
  });

  it("includes genre param when provided", async () => {
    mockGet.mockResolvedValue({ data: validResponse });

    const { result } = renderHook(
      () => useBooks({ page: 1, genre: 5 }),
      { wrapper: createWrapper() }
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockGet).toHaveBeenCalledWith("/books/", {
      params: { page: 1, limit: 24, genre: 5 },
    });
  });

  it("includes sort param when provided", async () => {
    mockGet.mockResolvedValue({ data: validResponse });

    const { result } = renderHook(
      () => useBooks({ page: 1, sort: "rating_desc" }),
      { wrapper: createWrapper() }
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockGet).toHaveBeenCalledWith("/books/", {
      params: { page: 1, limit: 24, sort: "rating_desc" },
    });
  });

  it("excludes sort param when undefined", async () => {
    mockGet.mockResolvedValue({ data: validResponse });

    const { result } = renderHook(
      () => useBooks({ page: 1 }),
      { wrapper: createWrapper() }
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockGet).toHaveBeenCalledWith("/books/", {
      params: { page: 1, limit: 24 },
    });
  });
});

describe("useSearchBooks", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("returns valid data for well-formed search response", async () => {
    mockGet.mockResolvedValue({ data: validResponse });

    const { result } = renderHook(
      () => useSearchBooks({ q: "test query", page: 1 }),
      { wrapper: createWrapper() }
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toEqual(validResponse);
  });

  it("is disabled when query is shorter than 2 characters", () => {
    mockGet.mockResolvedValue({ data: validResponse });

    const { result } = renderHook(
      () => useSearchBooks({ q: "a", page: 1 }),
      { wrapper: createWrapper() }
    );

    // Should not fetch
    expect(result.current.fetchStatus).toBe("idle");
    expect(mockGet).not.toHaveBeenCalled();
  });

  it("normalizes malformed search response", async () => {
    const malformed = { page: 1 };
    mockGet.mockResolvedValue({ data: malformed });

    const { result } = renderHook(
      () => useSearchBooks({ q: "test", page: 1, limit: 24 }),
      { wrapper: createWrapper() }
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data?.items).toEqual([]);
    expect(result.current.data?.total).toBe(0);
    expect(result.current.data?.limit).toBe(24);
  });
});
