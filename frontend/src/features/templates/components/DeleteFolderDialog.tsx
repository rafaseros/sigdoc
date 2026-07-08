import { toast } from "sonner";
import { CircleAlert, Trash2 } from "lucide-react";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

import { useDeleteFolder, type Folder } from "../api/folders";

interface DeleteFolderDialogProps {
  folder: Folder;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Called after a successful delete — lets the caller reset an active filter. */
  onDeleted?: () => void;
}

export function DeleteFolderDialog({
  folder,
  open,
  onOpenChange,
  onDeleted,
}: DeleteFolderDialogProps) {
  const deleteFolder = useDeleteFolder();

  function handleDelete() {
    deleteFolder.mutate(folder.id, {
      onSuccess: () => {
        toast.success("Carpeta eliminada con éxito");
        onOpenChange(false);
        onDeleted?.();
      },
      onError: (err: unknown) => {
        const detail =
          err &&
          typeof err === "object" &&
          "response" in err &&
          (err as { response?: { data?: { detail?: string } } }).response
            ?.data?.detail;
        toast.error((detail as string) || "Error al eliminar la carpeta");
      },
    });
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Eliminar carpeta</DialogTitle>
        </DialogHeader>

        <div className="flex items-start gap-2.5 rounded-[10px] bg-[var(--bg-accent)] px-3.5 py-3 text-[13px] leading-[1.45] text-[var(--primary)]">
          <CircleAlert className="mt-px size-4 shrink-0" />
          <div className="flex-1">
            Las plantillas no se eliminan; quedan sin carpeta.
          </div>
        </div>

        <DialogDescription>
          ¿Está seguro de eliminar la carpeta "{folder.name}"? Esta acción no
          se puede deshacer.
        </DialogDescription>

        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
          >
            Cancelar
          </Button>
          <Button
            type="button"
            onClick={handleDelete}
            disabled={deleteFolder.isPending}
            className="bg-[var(--destructive)] font-semibold text-white hover:bg-[#93000a]"
          >
            <Trash2 className="size-3.5" />
            {deleteFolder.isPending ? "Eliminando…" : "Eliminar"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
