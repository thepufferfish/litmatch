import { useQuery } from "@tanstack/react-query";
import api from "@/api/client";
import type { Genre } from "@/types";

export function useGenres() {
  return useQuery({
    queryKey: ["genres"],
    queryFn: async () => {
      const { data } = await api.get<Genre[]>("/genres/");
      return data;
    },
    staleTime: 10 * 60 * 1000,
  });
}
