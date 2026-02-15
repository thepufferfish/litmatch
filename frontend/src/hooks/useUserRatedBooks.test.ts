import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createElement, type ReactNode } from "react";
import {
  useUserRatedBooks,
  useUserRatings,
  useUserRatedBooksPaginated,
} from "./useUserRatedBooks";
import api from "@/api/client";
import type { Mock } from "vitest";
import type { Book, BookSortOption, PaginatedResponse, UserRating } from "@/types";

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
  title: "Rated Book",
  author_id: 1,
  publisher_id: 1,
  publish_date: "2024-01-01",
  description: "A rated book.",
  url: "https://example.com/rated",
  cover: null,
  author: { id: 1, name: "Test Author" },
  publisher: { id: 1, name: "Test Publisher" },
  genres: [{ id: 1, name: "Fiction" }],
  avg_critic_rating: 4.0,
  review_count: 3,
};

const mockBooksResponse: PaginatedResponse<Book> = {
  items: [mockBook],
  total: 1,
  page: 1,
  limit: 100,
};

const mockRating: UserRating = {
  id: 1,
  user_id: 10,
  book_id: 1,
  rating: 4,
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-01T00:00:00Z",
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

// -- Tests: useUserRatedBooks ------------------------------------------------

describe("useUserRatedBooks", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("fetches books with user_id param", async () => {
    mockGet.mockResolvedValue({ data: mockBooksResponse });

    const { result } = renderHook(() => useUserRatedBooks(10), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toEqual(mockBooksResponse);
    expect(mockGet).toHaveBeenCalledWith("/books/", {
      params: { user_id: 10, limit: 100 },
    });
  });

  it("is disabled when userId is undefined", () => {
    const { result } = renderHook(() => useUserRatedBooks(undefined), {
      wrapper: createWrapper(),
    });

    expect(result.current.fetchStatus).toBe("idle");
    expect(mockGet).not.toHaveBeenCalled();
  });
});

// -- Tests: useUserRatings ---------------------------------------------------

describe("useUserRatings", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("fetches ratings from /ratings/", async () => {
    mockGet.mockResolvedValue({ data: [mockRating] });

    const { result } = renderHook(() => useUserRatings(10), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toEqual([mockRating]);
    expect(mockGet).toHaveBeenCalledWith("/ratings/");
  });

  it("is disabled when userId is undefined", () => {
    const { result } = renderHook(() => useUserRatings(undefined), {
      wrapper: createWrapper(),
    });

    expect(result.current.fetchStatus).toBe("idle");
    expect(mockGet).not.toHaveBeenCalled();
  });
});

// -- Tests: useUserRatedBooksPaginated --------------------------------------

describe("useUserRatedBooksPaginated", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("fetches books with user_id, page, limit, and sort params", async () => {
    const paginatedResponse: PaginatedResponse<Book> = {
      items: [mockBook],
      total: 25,
      page: 2,
      limit: 12,
    };
    mockGet.mockResolvedValue({ data: paginatedResponse });

    const { result } = renderHook(
      () =>
        useUserRatedBooksPaginated(10, {
          page: 2,
          limit: 12,
          sort: "title_asc",
        }),
      { wrapper: createWrapper() }
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toEqual(paginatedResponse);
    expect(mockGet).toHaveBeenCalledWith("/books/", {
      params: { user_id: 10, page: 2, limit: 12, sort: "title_asc" },
    });
  });

  it("uses default page=1, limit=12 when not specified", async () => {
    mockGet.mockResolvedValue({ data: mockBooksResponse });

    const { result } = renderHook(
      () => useUserRatedBooksPaginated(10),
      { wrapper: createWrapper() }
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockGet).toHaveBeenCalledWith("/books/", {
      params: { user_id: 10, page: 1, limit: 12 },
    });
  });

  it("omits sort param when sort is undefined", async () => {
    mockGet.mockResolvedValue({ data: mockBooksResponse });

    const { result } = renderHook(
      () => useUserRatedBooksPaginated(10, { page: 1, limit: 12 }),
      { wrapper: createWrapper() }
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockGet).toHaveBeenCalledWith("/books/", {
      params: { user_id: 10, page: 1, limit: 12 },
    });
  });

  it("is disabled when userId is undefined", () => {
    const { result } = renderHook(
      () => useUserRatedBooksPaginated(undefined),
      { wrapper: createWrapper() }
    );

    expect(result.current.fetchStatus).toBe("idle");
    expect(mockGet).not.toHaveBeenCalled();
  });

  it("uses a separate query key from useUserRatedBooks", async () => {
    mockGet.mockResolvedValue({ data: mockBooksResponse });

    const wrapper = createWrapper();

    const { result: paginatedResult } = renderHook(
      () => useUserRatedBooksPaginated(10, { page: 1, limit: 12 }),
      { wrapper }
    );

    const { result: unpaginatedResult } = renderHook(
      () => useUserRatedBooks(10),
      { wrapper }
    );

    await waitFor(() => expect(paginatedResult.current.isSuccess).toBe(true));
    await waitFor(() => expect(unpaginatedResult.current.isSuccess).toBe(true));

    // Both hooks should have been called (separate caches)
    expect(mockGet).toHaveBeenCalledTimes(2);
  });

  it("includes sort in query key so different sorts use separate caches", async () => {
    mockGet.mockResolvedValue({ data: mockBooksResponse });

    const wrapper = createWrapper();

    const { result: ascResult } = renderHook(
      () =>
        useUserRatedBooksPaginated(10, {
          page: 1,
          limit: 12,
          sort: "title_asc" as BookSortOption,
        }),
      { wrapper }
    );

    const { result: descResult } = renderHook(
      () =>
        useUserRatedBooksPaginated(10, {
          page: 1,
          limit: 12,
          sort: "title_desc" as BookSortOption,
        }),
      { wrapper }
    );

    await waitFor(() => expect(ascResult.current.isSuccess).toBe(true));
    await waitFor(() => expect(descResult.current.isSuccess).toBe(true));

    // Separate query keys should trigger separate API calls
    expect(mockGet).toHaveBeenCalledTimes(2);
  });
});
