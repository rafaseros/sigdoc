import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/shared/lib/api-client";
import { documentKeys } from "./keys";

interface GenerateRequest {
  template_version_id: string;
  variables: Record<string, string>;
}

interface GenerateResponse {
  id: string;
  template_version_id: string;
  file_name: string;
  generation_type: string;
  status: string;
  download_url: string | null;
  variables_snapshot: Record<string, string>;
  created_at: string;
}

export function useGenerateDocument() {
  return useMutation({
    mutationFn: async (
      request: GenerateRequest,
    ): Promise<GenerateResponse> => {
      const { data } = await apiClient.post<GenerateResponse>(
        "/documents/generate",
        request,
      );
      return data;
    },
  });
}

export function useDownloadExcelTemplate() {
  return useMutation({
    mutationFn: async (templateVersionId: string) => {
      const response = await apiClient.get(
        `/documents/excel-template/${templateVersionId}`,
        { responseType: "blob" },
      );
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement("a");
      link.href = url;
      const filename =
        response.headers["content-disposition"]
          ?.split("filename=")[1]
          ?.replace(/"/g, "") || "bulk_template.xlsx";
      link.setAttribute("download", filename);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    },
  });
}

interface BulkGenerateResponse {
  batch_id: string;
  document_count: number;
  download_url: string;
  errors: Array<{ row: number; error: string }>;
}

export function useDeleteDocument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (documentId: string): Promise<void> => {
      await apiClient.delete(`/documents/${documentId}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: documentKeys.lists() });
    },
  });
}

export function useBulkGenerate() {
  return useMutation({
    mutationFn: async ({
      templateVersionId,
      file,
    }: {
      templateVersionId: string;
      file: File;
    }): Promise<BulkGenerateResponse> => {
      const formData = new FormData();
      formData.append("template_version_id", templateVersionId);
      formData.append("file", file);
      const { data } = await apiClient.post<BulkGenerateResponse>(
        "/documents/generate-bulk",
        formData,
        { headers: { "Content-Type": "multipart/form-data" } },
      );
      return data;
    },
  });
}
