export const userKeys = {
  all: ["users"] as const,
  lists: () => [...userKeys.all, "list"] as const,
  list: (filters: { page?: number; size?: number }) =>
    [...userKeys.lists(), filters] as const,
};
