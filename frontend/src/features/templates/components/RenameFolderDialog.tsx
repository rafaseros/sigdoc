import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Check, LoaderCircle } from "lucide-react";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

import { useRenameFolder, type Folder } from "../api/folders";

interface RenameFolderDialogProps {
  folder: Folder;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function RenameFolderDialog({
  folder,
  open,
  onOpenChange,
}: RenameFolderDialogProps) {
  const [name, setName] = useState(folder.name);

  // Re-sync with the latest folder name whenever the dialog (re)opens.
  useEffect(() => {
    if (open) setName(folder.name);
  }, [open, folder.name]);

  const renameFolder = useRenameFolder();

  const trimmedName = name.trim();
  const canSubmit =
    !!trimmedName && trimmedName !== folder.name && !renameFolder.isPending;

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;

    renameFolder.mutate(
      { folderId: folder.id, name: trimmedName },
      {
        onSuccess: () => {
          toast.success("Carpeta renombrada con éxito");
          onOpenChange(false);
        },
        onError: (err: unknown) => {
          const detail =
            err &&
            typeof err === "object" &&
            "response" in err &&
            (err as { response?: { data?: { detail?: string } } }).response
              ?.data?.detail;
          toast.error((detail as string) || "Error al renombrar la carpeta");
        },
      },
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle className="text-xl font-bold tracking-tight">
              Renombrar carpeta
            </DialogTitle>
            <DialogDescription>
              Cambie el nombre de la carpeta "{folder.name}".
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-1.5 py-4">
            <Label
              htmlFor="rename-folder-name"
              className="text-xs font-semibold uppercase tracking-[0.04em] text-[var(--fg-3)]"
            >
              Nombre
            </Label>
            <Input
              id="rename-folder-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Nombre de la carpeta"
              required
              autoFocus
            />
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              Cancelar
            </Button>
            <Button
              type="submit"
              disabled={!canSubmit}
              className="bg-gradient-to-br from-[#004ac6] to-[#2563eb] font-semibold text-white shadow-[var(--shadow-brand-sm)] hover:shadow-[var(--shadow-brand-md)]"
            >
              {renameFolder.isPending ? (
                <>
                  <LoaderCircle className="mr-2 size-4 animate-spin" />
                  Guardando...
                </>
              ) : (
                <>
                  <Check className="mr-2 size-4" />
                  Guardar cambios
                </>
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
