export const documentKeys = {
  all: ["documents"] as const,
  lists: () => [...documentKeys.all, "list"] as const,
  list: (filters: { page?: number; size?: number; template_id?: string }) =>
    [...documentKeys.lists(), filters] as const,
  /** Grouped listing (primary + related documents per generation). Kept as a
   * distinct key family from `lists()` so both the flat and grouped views can
   * be cached side by side and invalidated together on mutation. */
  groupLists: () => [...documentKeys.all, "group-list"] as const,
  groupList: (filters: {
    page?: number;
    size?: number;
    template_id?: string;
  }) => [...documentKeys.groupLists(), filters] as const,
  details: () => [...documentKeys.all, "detail"] as const,
  detail: (id: string) => [...documentKeys.details(), id] as const,
};
