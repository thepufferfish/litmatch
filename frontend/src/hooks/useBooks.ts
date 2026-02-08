import { useQuery } from "@tanstack/react-query";
import api from "@/api/client";
import type { Book, PaginatedResponse } from "@/types";

interface UseBooksParams {
  page?: number;
  limit?: number;
  genre?: number;
}

export function useBooks({ page = 1, limit = 24, genre }: UseBooksParams = {}) {
  return useQuery({
    queryKey: ["books", { page, limit, genre }],
    queryFn: async () => {
      const params: Record<string, number> = { page, limit };
      if (genre) params.genre = genre;
      const { data } = await api.get<PaginatedResponse<Book>>("/books/", {
        params,
      });
      return data;
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

interface UseSearchBooksParams {
  q: string;
  page?: number;
  limit?: number;
}

export function useSearchBooks({
  q,
  page = 1,
  limit = 24,
}: UseSearchBooksParams) {
  return useQuery({
    queryKey: ["books", { search: q, page, limit }],
    queryFn: async () => {
      const { data } = await api.get<PaginatedResponse<Book>>(
        "/books/search",
        {
          params: { q, page, limit },
        }
      );
      return data;
    },
    staleTime: 5 * 60 * 1000,
    enabled: q.length >= 2,
  });
}
