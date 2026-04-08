export const usageKeys = {
  all: ["usage"] as const,
  myUsage: (year: number, month: number) =>
    [...usageKeys.all, "my", year, month] as const,
  tenantUsage: (year: number, month: number) =>
    [...usageKeys.all, "tenant", year, month] as const,
};
