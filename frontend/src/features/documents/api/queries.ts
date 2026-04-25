import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/shared/lib/api-client";
import { documentKeys } from "./keys";

// ─── Download helpers ───────────────────────────────────────────────────────

export type DownloadFormat = "pdf" | "docx";
export type DownloadVia = "direct" | "share";

/** Build the download URL for a single document, including required format param. */
export function buildDownloadUrl(
  documentId: string,
  format: DownloadFormat,
  via: DownloadVia = "direct",
): string {
  const params = new URLSearchParams({ format, via });
  return `/documents/${documentId}/download?${params}`;
}

/** Build the bulk download URL for a batch. */
export function buildBulkDownloadUrl(
  batchId: string,
  format: DownloadFormat,
  includeBoth: boolean = false,
): string {
  const params = new URLSearchParams({ format });
  if (includeBoth) params.set("include_both", "true");
  return `/documents/bulk/${batchId}/download?${params}`;
}

/**
 * Trigger a browser download from a blob response.
 * Reusable utility shared by DynamicForm, DocumentList, and BulkGenerateFlow.
 */
export async function triggerBlobDownload(
  url: string,
  filename: string,
): Promise<void> {
  const response = await apiClient.get(url, { responseType: "blob" });
  const objectUrl = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement("a");
  link.href = objectUrl;
  link.setAttribute("download", filename);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(objectUrl);
}

export interface DocumentItem {
  id: string;
  template_version_id: string;
  file_name: string;
  generation_type: string;
  status: string;
  download_url?: string | null;
  variables_snapshot: Record<string, string>;
  created_at: string;
}

interface DocumentListResponse {
  items: DocumentItem[];
  total: number;
  page: number;
  size: number;
}

export function useDocuments(
  filters: { page?: number; size?: number; template_id?: string } = {},
) {
  return useQuery({
    queryKey: documentKeys.list(filters),
    queryFn: async () => {
      const params = new URLSearchParams();
      if (filters.page) params.set("page", String(filters.page));
      if (filters.size) params.set("size", String(filters.size));
      if (filters.template_id)
        params.set("template_id", filters.template_id);
      const { data } = await apiClient.get<DocumentListResponse>(
        `/documents?${params}`,
      );
      return data;
    },
  });
}
