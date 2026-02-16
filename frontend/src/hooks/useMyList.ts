import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "@/api/client";
import type { Book, BookSortOption, PaginatedResponse } from "@/types";

export function useMyListIds(userId: number | undefined) {
  const query = useQuery({
    queryKey: ["myListIds", userId],
    queryFn: async () => {
      const { data } = await api.get<number[]>("/list/ids");
      return new Set(data);
    },
    staleTime: 5 * 60 * 1000,
    enabled: !!userId,
  });

  return {
    ...query,
    data:
      query.data === undefined
        ? undefined
        : query.data instanceof Set
          ? query.data
          : new Set<number>(),
  };
}

interface UseMyListBooksPaginatedOptions {
  page?: number;
  limit?: number;
  sort?: BookSortOption;
}

export function useMyListBooksPaginated(
  userId: number | undefined,
  options: UseMyListBooksPaginatedOptions = {}
) {
  const { page = 1, limit = 12, sort } = options;

  return useQuery<PaginatedResponse<Book>>({
    queryKey: ["myListBooks", userId, { page, limit, sort }],
    queryFn: async () => {
      const params: Record<string, string | number> = { page, limit };
      if (sort) params.sort = sort;
      const { data } = await api.get<PaginatedResponse<Book>>(
        "/users/me/list/",
        { params }
      );
      return data;
    },
    staleTime: 5 * 60 * 1000,
    enabled: !!userId,
  });
}

export function useAddToList(userId?: number) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (bookId: number) => {
      await api.post("/list/", { book_id: bookId });
    },
    onMutate: async (bookId) => {
      if (!userId) return;
      const queryKey = ["myListIds", userId];
      await queryClient.cancelQueries({ queryKey });
      const previous = queryClient.getQueryData<Set<number>>(queryKey);
      const safeSet =
        previous instanceof Set ? previous : new Set<number>();
      const updated = new Set(safeSet);
      updated.add(bookId);
      queryClient.setQueryData(queryKey, updated);
      return { previous: safeSet };
    },
    onError: (_err, _bookId, context) => {
      if (context?.previous && userId) {
        queryClient.setQueryData(["myListIds", userId], context.previous);
      }
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["userProfile"] });
      void queryClient.invalidateQueries({ queryKey: ["myListBooks"] });
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: ["myListIds"] });
    },
  });
}

export function useRemoveFromList(userId?: number) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (bookId: number) => {
      await api.delete(`/list/${bookId}`);
    },
    onMutate: async (bookId) => {
      if (!userId) return;
      const queryKey = ["myListIds", userId];
      await queryClient.cancelQueries({ queryKey });
      const previous = queryClient.getQueryData<Set<number>>(queryKey);
      const safeSet =
        previous instanceof Set ? previous : new Set<number>();
      const updated = new Set(safeSet);
      updated.delete(bookId);
      queryClient.setQueryData(queryKey, updated);
      return { previous: safeSet };
    },
    onError: (_err, _bookId, context) => {
      if (context?.previous && userId) {
        queryClient.setQueryData(["myListIds", userId], context.previous);
      }
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["userProfile"] });
      void queryClient.invalidateQueries({ queryKey: ["myListBooks"] });
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: ["myListIds"] });
    },
  });
}
