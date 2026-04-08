import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/shared/lib/api-client";
import { templateKeys } from "./keys";

interface VariableMeta {
  name: string;
  contexts: string[];
}

interface TemplateVersion {
  id: string;
  version: number;
  variables: string[];
  variables_meta: VariableMeta[];
  file_size: number;
  created_at: string;
}

export interface Template {
  id: string;
  name: string;
  description: string | null;
  current_version: number;
  variables: string[];
  versions: TemplateVersion[];
  created_at: string;
  updated_at: string;
  access_type: "owned" | "shared" | "admin";
  is_owner: boolean;
}

interface TemplateListResponse {
  items: Template[];
  total: number;
  page: number;
  size: number;
}

export interface TemplateShare {
  id: string;
  template_id: string;
  user_id: string;
  user_email: string | null;
  tenant_id: string;
  shared_by: string;
  shared_at: string | null;
}

export function useTemplates(
  filters: { page?: number; size?: number; search?: string } = {}
) {
  return useQuery({
    queryKey: templateKeys.list(filters),
    queryFn: async () => {
      const params = new URLSearchParams();
      if (filters.page) params.set("page", String(filters.page));
      if (filters.size) params.set("size", String(filters.size));
      if (filters.search) params.set("search", filters.search);
      const { data } = await apiClient.get<TemplateListResponse>(
        `/templates?${params}`
      );
      return data;
    },
  });
}

export function useTemplate(id: string) {
  return useQuery({
    queryKey: templateKeys.detail(id),
    queryFn: async () => {
      const { data } = await apiClient.get<Template>(`/templates/${id}`);
      return data;
    },
    enabled: !!id,
  });
}

export function useTemplateShares(templateId: string) {
  return useQuery({
    queryKey: templateKeys.shares(templateId),
    queryFn: async () => {
      const { data } = await apiClient.get<TemplateShare[]>(
        `/templates/${templateId}/shares`
      );
      return data;
    },
    enabled: !!templateId,
  });
}
