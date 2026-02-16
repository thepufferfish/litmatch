import { useQuery } from "@tanstack/react-query";
import api from "@/api/client";
import type { Book, BookSortOption, PaginatedResponse } from "@/types";

/**
 * Normalize a paginated API response to ensure all required fields
 * are present with safe default values. Prevents NaN/Infinity from
 * propagating into pagination calculations.
 */
function normalizePaginatedResponse<T>(
  data: Partial<PaginatedResponse<T>>,
  fallbackLimit: number
): PaginatedResponse<T> {
  return {
    items: Array.isArray(data.items) ? data.items : [],
    total: typeof data.total === "number" && Number.isFinite(data.total) && data.total >= 0 ? data.total : 0,
    page: typeof data.page === "number" && Number.isFinite(data.page) && data.page >= 1 ? data.page : 1,
    limit: typeof data.limit === "number" && Number.isFinite(data.limit) && data.limit > 0
      ? data.limit
      : fallbackLimit,
  };
}

interface UseBooksParams {
  page?: number;
  limit?: number;
  genre?: number;
  sort?: BookSortOption;
  category?: "fiction" | "nonfiction";
  q?: string;
}

export function useBooks({ page = 1, limit = 24, genre, sort, category, q }: UseBooksParams = {}) {
  return useQuery({
    queryKey: ["books", { page, limit, genre, sort, category, q }],
    queryFn: async () => {
      const params: Record<string, string | number> = { page, limit };
      if (genre) params.genre = genre;
      if (sort) params.sort = sort;
      if (category) params.category = category;
      if (q) params.q = q;
      const { data } = await api.get<PaginatedResponse<Book>>("/books/", {
        params,
      });
      return normalizePaginatedResponse(data, limit);
    },
    staleTime: 5 * 60 * 1000,
  });
}

export function useBook(id: number) {
  return useQuery({
    queryKey: ["book", id],
    queryFn: async () => {
      const { data } = await api.get<Book>(`/books/${id}`);
      return data;
    },
    staleTime: 5 * 60 * 1000,
    enabled: !!id,
  });
}
