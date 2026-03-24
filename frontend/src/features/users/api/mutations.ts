import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/shared/lib/api-client";
import { userKeys } from "./keys";

export function useCreateUser() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (payload: {
      email: string;
      full_name: string;
      password: string;
    }) => {
      const { data } = await apiClient.post("/users", payload);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: userKeys.lists() });
    },
  });
}

export function useUpdateUser() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      id,
      ...payload
    }: {
      id: string;
      email?: string;
      full_name?: string;
      is_active?: boolean;
    }) => {
      const { data } = await apiClient.put(`/users/${id}`, payload);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: userKeys.lists() });
    },
  });
}

export function useDeactivateUser() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (id: string) => {
      await apiClient.delete(`/users/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: userKeys.lists() });
    },
  });
}

export function useChangePassword() {
  return useMutation({
    mutationFn: async (payload: {
      current_password: string;
      new_password: string;
    }) => {
      const { data } = await apiClient.post("/auth/change-password", payload);
      return data;
    },
  });
}
