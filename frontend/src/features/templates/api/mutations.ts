import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/shared/lib/api-client";
import { folderKeys, templateKeys } from "./keys";
import type { VariableType } from "./queries";

export interface ValidationError {
  type: string;
  message: string;
  variable: string | null;
  fixable: boolean;
  suggestion: string | null;
}

export interface VariableSummary {
  name: string;
  count: number;
  has_errors: boolean;
  contexts: string[];
}

export interface ValidationResult {
  valid: boolean;
  variables: string[];
  variable_summary: VariableSummary[];
  errors: ValidationError[];
  warnings: ValidationError[];
  has_fixable_errors: boolean;
  has_unfixable_errors: boolean;
}

export function useValidateTemplate() {
  return useMutation({
    mutationFn: async (file: File): Promise<ValidationResult> => {
      const formData = new FormData();
      formData.append("file", file);
      const { data } = await apiClient.post<ValidationResult>(
        "/templates/validate",
        formData,
        { headers: { "Content-Type": "multipart/form-data" } }
      );
      return data;
    },
  });
}

export function useAutoFixTemplate() {
  return useMutation({
    mutationFn: async (file: File) => {
      const formData = new FormData();
      formData.append("file", file);
      const response = await apiClient.post("/templates/auto-fix", formData, {
        headers: { "Content-Type": "multipart/form-data" },
        responseType: "blob",
      });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement("a");
      link.href = url;
      const filename = file.name.replace(".docx", "_corregido.docx");
      link.setAttribute("download", filename);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    },
  });
}

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
      // A deleted template may have belonged to a folder — its count must
      // refresh too.
      queryClient.invalidateQueries({ queryKey: folderKeys.lists() });
    },
  });
}

export function useUpdateTemplate() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      templateId,
      name,
      description,
      folder_id,
    }: {
      templateId: string;
      name?: string;
      description?: string;
      /** Explicit `null` unfiles the template ("Sin carpeta"); `undefined` leaves it untouched. */
      folder_id?: string | null;
    }) => {
      const { data } = await apiClient.patch(`/templates/${templateId}`, {
        name,
        description,
        folder_id,
      });
      return data;
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: templateKeys.lists() });
      queryClient.invalidateQueries({
        queryKey: templateKeys.detail(variables.templateId),
      });
      // Renaming never touches folder_id, but moving does — invalidate
      // folder counts unconditionally since this query is cheap and it
      // keeps the mutation simple (no conditional invalidation branch).
      queryClient.invalidateQueries({ queryKey: folderKeys.lists() });
    },
  });
}

export function useShareTemplate() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      templateId,
      email,
    }: {
      templateId: string;
      email: string;
    }) => {
      const { data } = await apiClient.post(
        `/templates/${templateId}/shares`,
        { email }
      );
      return data;
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: templateKeys.shares(variables.templateId),
      });
    },
  });
}

export function useUnshareTemplate() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      templateId,
      userId,
    }: {
      templateId: string;
      userId: string;
    }) => {
      await apiClient.delete(`/templates/${templateId}/shares/${userId}`);
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: templateKeys.shares(variables.templateId),
      });
    },
  });
}

export interface VariableTypeOverrideInput {
  name: string;
  type: VariableType;
  options?: string[] | null;
  help_text?: string | null;
}

export function useUpdateVariableTypes(templateId: string, versionId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (overrides: VariableTypeOverrideInput[]) => {
      const { data } = await apiClient.patch(
        `/templates/${templateId}/versions/${versionId}/variables-meta`,
        { overrides }
      );
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: templateKeys.detail(templateId),
      });
    },
  });
}
