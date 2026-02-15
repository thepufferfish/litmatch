import { useQuery } from "@tanstack/react-query";
import api from "@/api/client";
import type { Book, BookSortOption, PaginatedResponse, UserRating } from "@/types";

interface UseUserRatedBooksPaginatedOptions {
  page?: number;
  limit?: number;
  sort?: BookSortOption;
}

export function useUserRatedBooks() {
  return useQuery<PaginatedResponse<Book>>({
    queryKey: ["userRatedBooks"],
    queryFn: async () => {
      const { data } = await api.get<PaginatedResponse<Book>>(
        "/users/me/rated-books/",
        {
          params: { limit: 100 },
        }
      );
      return data;
    },
    staleTime: 5 * 60 * 1000,
  });
}

export function useUserRatedBooksPaginated(
  options: UseUserRatedBooksPaginatedOptions = {}
) {
  const { page = 1, limit = 12, sort } = options;

  return useQuery<PaginatedResponse<Book>>({
    queryKey: ["userRatedBooksPaginated", { page, limit, sort }],
    queryFn: async () => {
      const params: Record<string, string | number> = {
        page,
        limit,
      };
      if (sort) {
        params.sort = sort;
      }
      const { data } = await api.get<PaginatedResponse<Book>>(
        "/users/me/rated-books/",
        {
          params,
        }
      );
      return data;
    },
    staleTime: 5 * 60 * 1000,
  });
}

export function useUserRatings(userId: number | undefined) {
  return useQuery<UserRating[]>({
    queryKey: ["userRatings", userId],
    queryFn: async () => {
      const { data } = await api.get<UserRating[]>("/ratings/");
      return data;
    },
    staleTime: 5 * 60 * 1000,
    enabled: !!userId,
  });
}
