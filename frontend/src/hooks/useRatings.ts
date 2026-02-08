import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "@/api/client";
import type { UserRating, RatingCreate } from "@/types";

export function useUserRating(bookId: number, userId: number | undefined) {
  return useQuery({
    queryKey: ["rating", { bookId, userId }],
    queryFn: async () => {
      const { data } = await api.get<UserRating[]>("/ratings/", {
        params: { book_id: bookId, user_id: userId },
      });
      return data[0] ?? null;
    },
    staleTime: 5 * 60 * 1000,
    enabled: !!bookId && !!userId,
  });
}

export function useSubmitRating() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (rating: RatingCreate) => {
      const { data } = await api.post<UserRating>("/ratings/", rating);
      return data;
    },
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({
        queryKey: ["rating", { bookId: variables.book_id }],
        exact: false,
      });
    },
  });
}
