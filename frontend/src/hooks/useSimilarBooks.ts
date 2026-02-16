import { useQuery } from "@tanstack/react-query";
import api from "@/api/client";
import type { Book } from "@/types";

export function useSimilarBooks(bookId: number, enabled: boolean = true) {
  return useQuery({
    queryKey: ["similarBooks", bookId],
    queryFn: async () => {
      const { data } = await api.get<Book[]>(`/books/${bookId}/similar`);
      return data;
    },
    staleTime: 10 * 60 * 1000, // 10 minutes
    enabled: !!bookId && enabled,
  });
}
