import { useQuery } from "@tanstack/react-query";
import api from "@/api/client";
import type { GroupedGenres } from "@/types";

export function useGroupedGenres() {
  return useQuery({
    queryKey: ["genres", "grouped"],
    queryFn: async () => {
      const { data } = await api.get<GroupedGenres>("/genres/grouped");
      return data;
    },
    staleTime: 10 * 60 * 1000,
  });
}
