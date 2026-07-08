import { useState } from "react";
import { toast } from "sonner";
import { FolderPlus, LoaderCircle } from "lucide-react";

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

import { useCreateFolder } from "../api/folders";

interface CreateFolderDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function CreateFolderDialog({
  open,
  onOpenChange,
}: CreateFolderDialogProps) {
  const [name, setName] = useState("");
  const createFolder = useCreateFolder();

  function handleOpenChange(next: boolean) {
    onOpenChange(next);
    if (!next) setName("");
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) return;

    createFolder.mutate(trimmed, {
      onSuccess: () => {
        toast.success("Carpeta creada con éxito");
        handleOpenChange(false);
      },
      onError: (err: unknown) => {
        const detail =
          err &&
          typeof err === "object" &&
          "response" in err &&
          (err as { response?: { data?: { detail?: string } } }).response
            ?.data?.detail;
        toast.error((detail as string) || "Error al crear la carpeta");
      },
    });
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-md">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle className="text-xl font-bold tracking-tight">
              Nueva carpeta
            </DialogTitle>
            <DialogDescription>
              Organice sus plantillas agrupándolas en carpetas personales.
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-1.5 py-4">
            <Label
              htmlFor="folder-name"
              className="text-xs font-semibold uppercase tracking-[0.04em] text-[var(--fg-3)]"
            >
              Nombre de la carpeta
            </Label>
            <Input
              id="folder-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="ej. Contratos"
              autoFocus
              required
            />
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => handleOpenChange(false)}
            >
              Cancelar
            </Button>
            <Button
              type="submit"
              disabled={!name.trim() || createFolder.isPending}
              className="bg-gradient-to-br from-[#004ac6] to-[#2563eb] font-semibold text-white shadow-[var(--shadow-brand-sm)] hover:shadow-[var(--shadow-brand-md)]"
            >
              {createFolder.isPending ? (
                <>
                  <LoaderCircle className="mr-2 size-4 animate-spin" />
                  Creando...
                </>
              ) : (
                <>
                  <FolderPlus className="mr-2 size-4" />
                  Crear carpeta
                </>
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
