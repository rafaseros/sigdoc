export const templateKeys = {
  all: ["templates"] as const,
  lists: () => [...templateKeys.all, "list"] as const,
  list: (filters: { page?: number; size?: number; search?: string }) =>
    [...templateKeys.lists(), filters] as const,
  details: () => [...templateKeys.all, "detail"] as const,
  detail: (id: string) => [...templateKeys.details(), id] as const,
  shares: (templateId: string) =>
    [...templateKeys.all, "shares", templateId] as const,
};
