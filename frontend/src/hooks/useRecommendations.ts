import { useQuery } from "@tanstack/react-query";
import api from "@/api/client";
import type { RecommendationCategory, RecommendationResponse } from "@/types";

interface UseRecommendationsParams {
  category?: RecommendationCategory;
  limit?: number;
  enabled?: boolean;
  genreId?: number;
}

export function useRecommendations({
  category = "all",
  limit = 20,
  enabled = true,
  genreId,
}: UseRecommendationsParams = {}) {
  return useQuery<RecommendationResponse>({
    queryKey: ["recommendations", { category, limit, genreId }],
    queryFn: async () => {
      const params: Record<string, string | number> = { category, limit };
      if (genreId) params.genre_id = genreId;
      const { data } = await api.get<RecommendationResponse>(
        "/recommendations/",
        { params }
      );
      return data;
    },
    staleTime: 5 * 60 * 1000,
    enabled,
  });
}
