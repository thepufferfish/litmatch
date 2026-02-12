import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "@/api/client";
import type { UserRating, RatingCreate } from "@/types";

export function useUserRating(bookId: number, userId: number | undefined) {
  return useQuery({
    queryKey: ["rating", { bookId, userId }],
    queryFn: async () => {
      const { data } = await api.get<UserRating[]>("/ratings/", {
        params: { book_id: bookId },
      });
      return data[0] ?? null;
    },
    staleTime: 5 * 60 * 1000,
    enabled: !!bookId && !!userId,
  });
}

export function useUserRatingsMap(userId: number | undefined) {
  return useQuery({
    queryKey: ["userRatings", userId],
    queryFn: async () => {
      const { data } = await api.get<UserRating[]>("/ratings/");
      const map = new Map<number, number>();
      for (const r of data) {
        map.set(r.book_id, r.rating);
      }
      return map;
    },
    staleTime: 5 * 60 * 1000,
    enabled: !!userId,
  });
}

export function useSubmitRating(userId?: number) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (rating: RatingCreate) => {
      const { data } = await api.post<UserRating>("/ratings/", rating);
      return data;
    },
    onMutate: async (variables) => {
      if (!userId) return;
      const queryKey = ["userRatings", userId];
      await queryClient.cancelQueries({ queryKey });
      const previous = queryClient.getQueryData<Map<number, number>>(queryKey);
      const updated = new Map(previous ?? []);
      updated.set(variables.book_id, variables.rating);
      queryClient.setQueryData(queryKey, updated);
      return { previous: previous ?? new Map<number, number>() };
    },
    onError: (_err, _variables, context) => {
      if (context?.previous && userId) {
        queryClient.setQueryData(["userRatings", userId], context.previous);
      }
    },
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({
        queryKey: ["rating", { bookId: variables.book_id }],
        exact: false,
      });
      void queryClient.invalidateQueries({ queryKey: ["recommendations"] });
      void queryClient.invalidateQueries({ queryKey: ["userProfile"] });
      void queryClient.invalidateQueries({ queryKey: ["userRatedBooks"] });
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: ["userRatings"] });
    },
  });
}

export function useDeleteRating(userId?: number) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (bookId: number) => {
      await api.delete(`/ratings/${bookId}`);
    },
    onMutate: async (bookId) => {
      if (!userId) return;
      const queryKey = ["userRatings", userId];
      await queryClient.cancelQueries({ queryKey });
      const previous = queryClient.getQueryData<Map<number, number>>(queryKey);
      const updated = new Map(previous ?? []);
      updated.delete(bookId);
      queryClient.setQueryData(queryKey, updated);
      return { previous: previous ?? new Map<number, number>() };
    },
    onError: (_err, _bookId, context) => {
      if (context?.previous && userId) {
        queryClient.setQueryData(["userRatings", userId], context.previous);
      }
    },
    onSuccess: (_data, bookId) => {
      void queryClient.invalidateQueries({
        queryKey: ["rating", { bookId }],
        exact: false,
      });
      void queryClient.invalidateQueries({ queryKey: ["recommendations"] });
      void queryClient.invalidateQueries({ queryKey: ["userProfile"] });
      void queryClient.invalidateQueries({ queryKey: ["userRatedBooks"] });
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: ["userRatings"] });
    },
  });
}
