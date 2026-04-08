export const subscriptionKeys = {
  all: ["subscription"] as const,
  tiers: () => [...subscriptionKeys.all, "tiers"] as const,
  tenantTier: () => [...subscriptionKeys.all, "tenant-tier"] as const,
};
