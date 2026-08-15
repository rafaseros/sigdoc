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
 * Build the combined-ZIP download URL for a document group. The endpoint
 * streams a single ZIP of the primary + related documents in the requested
 * format. Non-admins may only request `pdf` (the backend 403s on `docx`),
 * mirroring the per-document rule enforced by {@link buildDownloadUrl}.
 */
export function buildGroupDownloadUrl(
  groupId: string,
  format: DownloadFormat,
): string {
  const params = new URLSearchParams({ format });
  return `/documents/groups/${groupId}/download?${params}`;
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
  /** Template that produced this document. */
  template_id: string;
  template_name: string;
  /** Human version number of the template version used (not the version row id). */
  template_version: number;
  docx_file_name: string;
  pdf_file_name: string | null;
  generation_type: string;
  status: string;
  download_url?: string | null;
  variables_snapshot: Record<string, string>;
  created_at: string;
  /** Groups the documents produced by one generate call over a version with
   * related files; `null` for single-file generations. */
  group_id: string | null;
  /** For a related document, the label configured on the version's related
   * file (e.g. "Recibo de pago"). `null` for a primary or standalone
   * document. */
  related_label: string | null;
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

/** One generated document with its related documents grouped beneath it. */
export interface DocumentGroup {
  /** Shared id linking a primary to its related documents; `null` for a
   * standalone document generated without related files. */
  group_id: string | null;
  /** The primary document produced by the generation. */
  primary: DocumentItem;
  /** Related documents produced alongside the primary; `[]` when standalone. */
  related: DocumentItem[];
}

interface DocumentGroupsResponse {
  items: DocumentGroup[];
  /** Number of GROUPS — the pagination unit — not individual documents. */
  total: number;
  page: number;
  size: number;
}

/**
 * Grouped listing of generated documents: each item is a primary document
 * with any related documents nested beneath it. Mirrors {@link useDocuments}
 * filters/keys but hits the `/documents/groups` endpoint and is cached under a
 * distinct key family. The flat {@link useDocuments} hook is intentionally
 * kept for other consumers (e.g. the template detail count).
 */
export function useDocumentGroups(
  filters: { page?: number; size?: number; template_id?: string } = {},
) {
  return useQuery({
    queryKey: documentKeys.groupList(filters),
    queryFn: async () => {
      const params = new URLSearchParams();
      if (filters.page) params.set("page", String(filters.page));
      if (filters.size) params.set("size", String(filters.size));
      if (filters.template_id)
        params.set("template_id", filters.template_id);
      const { data } = await apiClient.get<DocumentGroupsResponse>(
        `/documents/groups?${params}`,
      );
      return data;
    },
  });
}
