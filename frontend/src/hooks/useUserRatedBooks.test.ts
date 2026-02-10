import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createElement, type ReactNode } from "react";
import { useUserRatedBooks, useUserRatings } from "./useUserRatedBooks";
import api from "@/api/client";
import type { Mock } from "vitest";
import type { Book, PaginatedResponse, UserRating } from "@/types";

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
