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
import { Textarea } from "@/components/ui/textarea";

import { useUpdateTemplate } from "../api/mutations";

interface RenameTemplateDialogProps {
  templateId: string;
  currentName: string;
  currentDescription: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function RenameTemplateDialog({
  templateId,
  currentName,
  currentDescription,
  open,
  onOpenChange,
}: RenameTemplateDialogProps) {
  const [name, setName] = useState(currentName);
  const [description, setDescription] = useState(currentDescription ?? "");

  // Re-sync the draft fields with the latest template data whenever the
  // dialog is (re)opened — avoids showing stale values from a previous open.
  useEffect(() => {
    if (open) {
      setName(currentName);
      setDescription(currentDescription ?? "");
    }
  }, [open, currentName, currentDescription]);

  const updateTemplate = useUpdateTemplate();

  const trimmedName = name.trim();
  const nameChanged = trimmedName !== currentName;
  const descriptionChanged = description !== (currentDescription ?? "");
  const hasChanges = nameChanged || descriptionChanged;
  const canSubmit = !!trimmedName && hasChanges && !updateTemplate.isPending;

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;

    updateTemplate.mutate(
      {
        templateId,
        ...(nameChanged ? { name: trimmedName } : {}),
        ...(descriptionChanged ? { description } : {}),
      },
      {
        onSuccess: () => {
          toast.success("Plantilla renombrada con éxito");
          onOpenChange(false);
        },
        onError: (err: unknown) => {
          const detail =
            err &&
            typeof err === "object" &&
            "response" in err &&
            (err as { response?: { data?: { detail?: string } } }).response
              ?.data?.detail;
          toast.error((detail as string) || "Error al renombrar la plantilla");
        },
      },
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Renombrar plantilla</DialogTitle>
            <DialogDescription>
              Cambie el nombre o la descripción de la plantilla. Los cambios
              se aplican de inmediato.
            </DialogDescription>
          </DialogHeader>

          <div className="flex flex-col gap-4 py-4">
            <div className="grid gap-1.5">
              <Label
                htmlFor="rename-name"
                className="text-[12.5px] font-medium text-[var(--fg-2)]"
              >
                Nombre
              </Label>
              <Input
                id="rename-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Nombre de la plantilla"
                required
              />
            </div>

            <div className="grid gap-1.5">
              <Label
                htmlFor="rename-description"
                className="text-[12.5px] font-medium text-[var(--fg-2)]"
              >
                Descripción
              </Label>
              <Textarea
                id="rename-description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Descripción opcional"
                rows={3}
              />
            </div>
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
              className="bg-gradient-to-br from-[#004ac6] to-[#2563eb] font-semibold text-white shadow-[var(--shadow-brand-sm)] hover:shadow-[var(--shadow-brand-md)] disabled:opacity-60"
            >
              {updateTemplate.isPending ? (
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
