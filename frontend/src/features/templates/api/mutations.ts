import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/shared/lib/api-client";
import { folderKeys, templateKeys } from "./keys";
import type { ComputedConfig, TemplateStructure, VariableType } from "./queries";
import type { VariableMapping } from "../lib/fromExample";

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

interface AnalyzeExampleResponse {
  structure: TemplateStructure;
}

/** POST /templates/analyze-example — extract the structure of a filled
 * example .docx (no storage). Any authenticated user. */
export function useAnalyzeExample() {
  return useMutation({
    mutationFn: async (file: File): Promise<TemplateStructure> => {
      const formData = new FormData();
      formData.append("file", file);
      const { data } = await apiClient.post<AnalyzeExampleResponse>(
        "/templates/analyze-example",
        formData,
        { headers: { "Content-Type": "multipart/form-data" } }
      );
      return data.structure;
    },
  });
}

export interface TemplateFromExampleResponse {
  id: string;
  name: string;
  description: string | null;
  version: number;
  variables: string[];
  created_at: string;
}

/** POST /templates/from-example — create a template v1 from a filled
 * example .docx plus text→variable mappings (sent as a JSON string form
 * field, per the backend contract). Requires the template-manager role. */
export function useCreateTemplateFromExample() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      file,
      name,
      description,
      mappings,
    }: {
      file: File;
      name: string;
      description?: string;
      mappings: VariableMapping[];
    }): Promise<TemplateFromExampleResponse> => {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("name", name);
      if (description) formData.append("description", description);
      formData.append("mappings", JSON.stringify(mappings));

      const { data } = await apiClient.post<TemplateFromExampleResponse>(
        "/templates/from-example",
        formData,
        { headers: { "Content-Type": "multipart/form-data" } }
      );
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

/** POST /templates/{tid}/versions/{vid}/files — attach a related docx
 * (multipart `file` + form `label`) to the CURRENT version. Owner-or-admin
 * plus the template-manager role, enforced server-side. */
export function useAttachVersionFile() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      templateId,
      versionId,
      file,
      label,
    }: {
      templateId: string;
      versionId: string;
      file: File;
      label: string;
    }) => {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("label", label);

      const { data } = await apiClient.post(
        `/templates/${templateId}/versions/${versionId}/files`,
        formData,
        { headers: { "Content-Type": "multipart/form-data" } }
      );
      return data;
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: templateKeys.detail(variables.templateId),
      });
    },
  });
}

/** POST /templates/{tid}/versions/{vid}/files/from-example — attach a
 * related docx built from a FILLED example document: the backend rewrites
 * each mapped literal text into a {{ placeholder }} and then runs the
 * standard attach pipeline. `mappings` travels as a JSON string form field,
 * same schema as /templates/from-example. Same gates as the plain attach. */
export function useAttachVersionFileFromExample() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      templateId,
      versionId,
      file,
      label,
      mappings,
    }: {
      templateId: string;
      versionId: string;
      file: File;
      label: string;
      mappings: VariableMapping[];
    }) => {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("label", label);
      formData.append("mappings", JSON.stringify(mappings));

      const { data } = await apiClient.post(
        `/templates/${templateId}/versions/${versionId}/files/from-example`,
        formData,
        { headers: { "Content-Type": "multipart/form-data" } }
      );
      return data;
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: templateKeys.detail(variables.templateId),
      });
    },
  });
}

/** DELETE /templates/{tid}/versions/{vid}/files/{fileId} — remove a related
 * docx from the CURRENT version. Same gates as attach. */
export function useDetachVersionFile() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      templateId,
      versionId,
      fileId,
    }: {
      templateId: string;
      versionId: string;
      fileId: string;
    }) => {
      await apiClient.delete(
        `/templates/${templateId}/versions/${versionId}/files/${fileId}`
      );
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: templateKeys.detail(variables.templateId),
      });
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
  /** `null` clears any computed config; omitted leaves it untouched server-side. */
  computed?: ComputedConfig;
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
