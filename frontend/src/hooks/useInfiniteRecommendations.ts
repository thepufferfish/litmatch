import { useInfiniteQuery } from "@tanstack/react-query";
import api from "@/api/client";
import type {
  PaginatedRecommendationResponse,
  RecommendationCategory,
} from "@/types";

const PAGE_SIZE = 20;

interface UseInfiniteRecommendationsParams {
  category?: RecommendationCategory;
  enabled?: boolean;
  genreId?: number;
}

export function useInfiniteRecommendations({
  category = "all",
  enabled = true,
  genreId,
}: UseInfiniteRecommendationsParams = {}) {
  return useInfiniteQuery<PaginatedRecommendationResponse>({
    queryKey: ["recommendations", { category, genreId }],
    queryFn: async ({ pageParam }) => {
      const params: Record<string, string | number> = {
        category,
        limit: PAGE_SIZE,
        offset: pageParam as number,
      };
      if (genreId !== undefined) params.genre_id = genreId;
      const { data } = await api.get<PaginatedRecommendationResponse>(
        "/recommendations/",
        { params }
      );
      return data;
    },
    getNextPageParam: (lastPage) =>
      lastPage.has_more ? lastPage.offset + lastPage.limit : undefined,
    initialPageParam: 0,
    staleTime: 5 * 60 * 1000,
    enabled,
  });
}
