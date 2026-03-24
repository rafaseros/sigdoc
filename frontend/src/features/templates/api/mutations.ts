import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/shared/lib/api-client";
import { templateKeys } from "./keys";

export function useUploadTemplate() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      file,
      name,
      description,
    }: {
      file: File;
      name: string;
      description?: string;
    }) => {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("name", name);
      if (description) formData.append("description", description);

      const { data } = await apiClient.post("/templates/upload", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: templateKeys.lists() });
    },
  });
}

export function useUploadNewVersion() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      templateId,
      file,
    }: {
      templateId: string;
      file: File;
    }) => {
      const formData = new FormData();
      formData.append("file", file);

      const { data } = await apiClient.post(
        `/templates/${templateId}/versions`,
        formData,
        { headers: { "Content-Type": "multipart/form-data" } }
      );
      return data;
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: templateKeys.detail(variables.templateId),
      });
      queryClient.invalidateQueries({ queryKey: templateKeys.lists() });
    },
  });
}

export function useDeleteTemplate() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (id: string) => {
      await apiClient.delete(`/templates/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: templateKeys.lists() });
    },
  });
}
