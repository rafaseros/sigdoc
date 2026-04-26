import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/shared/lib/api-client";
import { subscriptionKeys } from "./keys";

// ─── Types matching backend schemas ────────────────────────────────────────

export interface TierPublic {
  id: string;
  name: string;
  slug: string;
  monthly_document_limit: number | null;
  max_templates: number | null;
  max_users: number | null;
  bulk_generation_limit: number;
  max_template_shares: number | null;
}

export interface TiersListResponse {
  items: TierPublic[];
  total: number;
}

export interface ResourceUsage {
  used: number;
  limit: number | null;
  percentage_used: number | null;
  near_limit: boolean;
}

export interface UsageSummary {
  documents: ResourceUsage;
  templates: ResourceUsage;
  users: ResourceUsage;
}

export interface TenantTierResponse {
  tier: TierPublic;
  usage: UsageSummary;
}

// ─── Hooks ─────────────────────────────────────────────────────────────────

export function useTiers() {
  return useQuery({
    queryKey: subscriptionKeys.tiers(),
    queryFn: async () => {
      const { data } = await apiClient.get<TiersListResponse>("/tiers");
      return data;
    },
  });
}

export function useTenantTier() {
  return useQuery({
    queryKey: subscriptionKeys.tenantTier(),
    queryFn: async () => {
      const { data } = await apiClient.get<TenantTierResponse>("/tiers/tenant");
      return data;
    },
  });
}
