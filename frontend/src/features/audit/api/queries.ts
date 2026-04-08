import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/shared/lib/api-client";
import { auditKeys, type AuditFilters } from "./keys";

export interface AuditLogEntry {
  id: string;
  actor_id: string | null;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  details: Record<string, unknown> | null;
  ip_address: string | null;
  created_at: string;
}

export interface AuditLogListResponse {
  items: AuditLogEntry[];
  total: number;
  page: number;
  size: number;
}

export function useAuditLog(
  page: number,
  size: number,
  filters: AuditFilters = {}
) {
  return useQuery({
    queryKey: auditKeys.list(page, size, filters),
    queryFn: async () => {
      const params = new URLSearchParams();
      params.set("page", String(page));
      params.set("size", String(size));
      if (filters.action) params.set("action", filters.action);
      if (filters.actor_id) params.set("actor_id", filters.actor_id);
      if (filters.date_from) params.set("date_from", filters.date_from);
      if (filters.date_to) params.set("date_to", filters.date_to);
      const { data } = await apiClient.get<AuditLogListResponse>(
        `/audit-log?${params}`
      );
      return data;
    },
  });
}
