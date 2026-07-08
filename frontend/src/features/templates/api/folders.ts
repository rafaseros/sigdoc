import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/shared/lib/api-client";
import { folderKeys, templateKeys } from "./keys";

export interface Folder {
  id: string;
  name: string;
  template_count: number;
}

interface FoldersResponse {
  folders: Folder[];
}

export function useFolders() {
  return useQuery({
    queryKey: folderKeys.lists(),
    queryFn: async () => {
      const { data } = await apiClient.get<FoldersResponse>("/folders");
      return data.folders ?? [];
    },
  });
}

export function useCreateFolder() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (name: string) => {
      const { data } = await apiClient.post<Folder>("/folders", { name });
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: folderKeys.lists() });
    },
  });
}

export function useRenameFolder() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      folderId,
      name,
    }: {
      folderId: string;
      name: string;
    }) => {
      const { data } = await apiClient.patch<Folder>(`/folders/${folderId}`, {
        name,
      });
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: folderKeys.lists() });
    },
  });
}

export function useDeleteFolder() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (folderId: string) => {
      await apiClient.delete(`/folders/${folderId}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: folderKeys.lists() });
      // Deleting a folder unfiles its templates server-side — the template
      // list (counts, folder_id) must refresh too, not just the folder list.
      queryClient.invalidateQueries({ queryKey: templateKeys.lists() });
    },
  });
}
