import { useQuery } from "@tanstack/react-query";
import api from "@/api/client";
import type { Review } from "@/types";

export function useReviews(bookId: number) {
  return useQuery({
    queryKey: ["reviews", bookId],
    queryFn: async () => {
      const { data } = await api.get<Review[]>(`/reviews/${bookId}`);
      return data;
    },
    staleTime: 5 * 60 * 1000,
    enabled: !!bookId,
  });
}
