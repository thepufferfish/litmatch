import { useQuery } from "@tanstack/react-query";
import api from "@/api/client";
import type { Book, PaginatedResponse, UserRating } from "@/types";

export function useUserRatedBooks(userId: number | undefined) {
  return useQuery<PaginatedResponse<Book>>({
    queryKey: ["userRatedBooks", userId],
    queryFn: async () => {
      const { data } = await api.get<PaginatedResponse<Book>>("/books/", {
        params: { user_id: userId, limit: 100 },
      });
      return data;
    },
    staleTime: 5 * 60 * 1000,
    enabled: !!userId,
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
