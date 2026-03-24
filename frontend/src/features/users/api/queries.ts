import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/shared/lib/api-client";
import { userKeys } from "./keys";

export interface UserResponse {
  id: string;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
  created_at: string;
}

interface UserListResponse {
  items: UserResponse[];
  total: number;
  page: number;
  size: number;
}

export function useUsers(filters: { page?: number; size?: number } = {}) {
  return useQuery({
    queryKey: userKeys.list(filters),
    queryFn: async () => {
      const params = new URLSearchParams();
      if (filters.page) params.set("page", String(filters.page));
      if (filters.size) params.set("size", String(filters.size));
      const { data } = await apiClient.get<UserListResponse>(
        `/users?${params}`
      );
      return data;
    },
  });
}
