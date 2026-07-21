export const templateKeys = {
  all: ["templates"] as const,
  lists: () => [...templateKeys.all, "list"] as const,
  list: (filters: {
    page?: number;
    size?: number;
    search?: string;
    folder_id?: string;
  }) => [...templateKeys.lists(), filters] as const,
  details: () => [...templateKeys.all, "detail"] as const,
  detail: (id: string) => [...templateKeys.details(), id] as const,
  shares: (templateId: string) =>
    [...templateKeys.all, "shares", templateId] as const,
  structure: (templateId: string, versionId: string, fileId?: string) =>
    fileId
      ? ([...templateKeys.all, "structure", templateId, versionId, fileId] as const)
      : ([...templateKeys.all, "structure", templateId, versionId] as const),
};

export const folderKeys = {
  all: ["folders"] as const,
  lists: () => [...folderKeys.all, "list"] as const,
};

export const presetKeys = {
  all: ["presets"] as const,
  lists: () => [...presetKeys.all, "list"] as const,
  list: (templateId: string) => [...presetKeys.lists(), templateId] as const,
};
