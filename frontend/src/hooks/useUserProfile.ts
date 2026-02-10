import { useQuery } from "@tanstack/react-query";
import api from "@/api/client";
import type { UserProfile } from "@/types";

export function useUserProfile(enabled: boolean = true) {
  return useQuery<UserProfile>({
    queryKey: ["userProfile"],
    queryFn: async () => {
      const { data } = await api.get<UserProfile>("/users/me");
      return data;
    },
    staleTime: 5 * 60 * 1000,
    enabled,
  });
}
