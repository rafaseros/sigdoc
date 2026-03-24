import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/shared/lib/api-client";
import { documentKeys } from "./keys";

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
