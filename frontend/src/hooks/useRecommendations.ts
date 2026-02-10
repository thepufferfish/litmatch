import { useQuery } from "@tanstack/react-query";
import api from "@/api/client";
import type { RecommendationCategory, RecommendationResponse } from "@/types";

interface UseRecommendationsParams {
  category?: RecommendationCategory;
  limit?: number;
  enabled?: boolean;
}

export function useRecommendations({
  category = "all",
  limit = 20,
  enabled = true,
}: UseRecommendationsParams = {}) {
  return useQuery<RecommendationResponse>({
    queryKey: ["recommendations", { category, limit }],
    queryFn: async () => {
      const { data } = await api.get<RecommendationResponse>(
        "/recommendations/",
        { params: { category, limit } }
      );
      return data;
    },
    staleTime: 5 * 60 * 1000,
    enabled,
  });
}
