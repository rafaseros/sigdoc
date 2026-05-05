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
      role?: string;
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
      role?: string;
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
    mutationFn: async (input: string | { id: string; reassignTo?: string }) => {
      // Backwards compatible: accept either a bare id (legacy) or
      // { id, reassignTo? }. Backend uses ?reassign_to=<uuid> when the
      // user owns templates that must be transferred before deactivation.
      const id = typeof input === "string" ? input : input.id;
      const reassignTo =
        typeof input === "string" ? undefined : input.reassignTo;
      const url = reassignTo
        ? `/users/${id}?reassign_to=${reassignTo}`
        : `/users/${id}`;
      await apiClient.delete(url);
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

export function useResetUserPassword() {
  return useMutation({
    mutationFn: async (payload: { id: string; new_password: string }) => {
      const { data } = await apiClient.post(
        `/users/${payload.id}/reset-password`,
        { new_password: payload.new_password },
      );
      return data;
    },
  });
}
