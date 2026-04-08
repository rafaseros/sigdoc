export interface AuditFilters {
  action?: string;
  actor_id?: string;
  date_from?: string;
  date_to?: string;
}

export const auditKeys = {
  all: ["audit"] as const,
  lists: () => [...auditKeys.all, "list"] as const,
  list: (page: number, size: number, filters: AuditFilters) =>
    [...auditKeys.lists(), page, size, filters] as const,
};
