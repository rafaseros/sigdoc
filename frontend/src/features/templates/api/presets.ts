import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/shared/lib/api-client";
import { presetKeys } from "./keys";

export interface Preset {
  id: string;
  name: string;
  values: Record<string, string>;
  created_by: string;
  created_at: string;
}

interface PresetsResponse {
  presets: Preset[];
}

/** Anyone with access to the template can list its presets — backend
 * enforces the permission check, no ownership gate needed here. */
export function usePresets(templateId: string) {
  return useQuery({
    queryKey: presetKeys.list(templateId),
    queryFn: async () => {
      const { data } = await apiClient.get<PresetsResponse>(
        `/templates/${templateId}/presets`,
      );
      return data.presets ?? [];
    },
    enabled: !!templateId,
  });
}

export function useCreatePreset(templateId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      name,
      values,
    }: {
      name: string;
      values: Record<string, string>;
    }) => {
      const { data } = await apiClient.post<Preset>(
        `/templates/${templateId}/presets`,
        { name, values },
      );
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: presetKeys.list(templateId) });
    },
  });
}

export function useUpdatePreset(templateId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      presetId,
      name,
      values,
    }: {
      presetId: string;
      name?: string;
      values?: Record<string, string>;
    }) => {
      const { data } = await apiClient.patch<Preset>(
        `/templates/${templateId}/presets/${presetId}`,
        { name, values },
      );
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: presetKeys.list(templateId) });
    },
  });
}

export function useDeletePreset(templateId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (presetId: string) => {
      await apiClient.delete(`/templates/${templateId}/presets/${presetId}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: presetKeys.list(templateId) });
    },
  });
}
