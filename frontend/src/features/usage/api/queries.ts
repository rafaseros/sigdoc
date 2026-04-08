import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/shared/lib/api-client";
import { usageKeys } from "./keys";

export interface TemplateUsageStat {
  template_id: string;
  template_name: string | null;
  document_count: number;
}

export interface UserUsageResponse {
  user_id: string;
  year: number;
  month: number;
  total_documents: number;
  by_template: TemplateUsageStat[];
}

export interface UserUsageStat {
  user_id: string;
  user_email: string;
  full_name: string | null;
  document_count: number;
}

export interface TenantUsageResponse {
  tenant_id: string;
  year: number;
  month: number;
  total_documents: number;
  by_user: UserUsageStat[];
}

export function useMyUsage(year: number, month: number) {
  return useQuery({
    queryKey: usageKeys.myUsage(year, month),
    queryFn: async () => {
      const params = new URLSearchParams({
        year: String(year),
        month: String(month),
      });
      const { data } = await apiClient.get<UserUsageResponse>(
        `/usage?${params}`
      );
      return data;
    },
  });
}

export function useTenantUsage(year: number, month: number) {
  return useQuery({
    queryKey: usageKeys.tenantUsage(year, month),
    queryFn: async () => {
      const params = new URLSearchParams({
        year: String(year),
        month: String(month),
      });
      const { data } = await apiClient.get<TenantUsageResponse>(
        `/usage/tenant?${params}`
      );
      return data;
    },
  });
}
