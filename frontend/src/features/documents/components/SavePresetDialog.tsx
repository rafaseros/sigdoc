/**
 * SavePresetDialog.tsx
 *
 * Opened from the sticky action bar's "Guardar datos" button (Feature A).
 * Persists the current, already-filtered non-computed values as a reusable
 * preset for this template. The caller is responsible for excluding empty
 * and computed entries before passing `values` in — see FullDocumentEditor's
 * `nonComputedValues`.
 */
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

import { useCreatePreset } from "@/features/templates/api/presets";

interface SavePresetDialogProps {
  templateId: string;
  /** Current, non-computed values — empty entries are dropped before POST. */
  values: Record<string, string>;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function nonEmptyValues(values: Record<string, string>): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [key, value] of Object.entries(values)) {
    if (value.trim().length > 0) out[key] = value;
  }
  return out;
}

export function SavePresetDialog({
  templateId,
  values,
  open,
  onOpenChange,
}: SavePresetDialogProps) {
  const [name, setName] = useState("");

  // Reset the draft name every time the dialog (re)opens.
  useEffect(() => {
    if (open) setName("");
  }, [open]);

  const createPreset = useCreatePreset(templateId);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) return;

    createPreset.mutate(
      { name: trimmed, values: nonEmptyValues(values) },
      {
        onSuccess: () => {
          toast.success(`Datos «${trimmed}» guardados`);
          onOpenChange(false);
        },
        onError: (err: unknown) => {
          const detail =
            err &&
            typeof err === "object" &&
            "response" in err &&
            (err as { response?: { data?: { detail?: string } } }).response
              ?.data?.detail;
          toast.error((detail as string) || "Error al guardar los datos");
        },
      },
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Guardar datos</DialogTitle>
            <DialogDescription>
              Guarde los valores actuales para reutilizarlos en próximas
              generaciones de esta plantilla.
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-1.5 py-4">
            <Label
              htmlFor="save-preset-name"
              className="text-[12.5px] font-medium text-[var(--fg-2)]"
            >
              Nombre
            </Label>
            <Input
              id="save-preset-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="ej. Cliente Acme"
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
              disabled={!name.trim() || createPreset.isPending}
              className="bg-gradient-to-br from-[#004ac6] to-[#2563eb] font-semibold text-white shadow-[var(--shadow-brand-sm)] hover:shadow-[var(--shadow-brand-md)] disabled:opacity-60"
            >
              {createPreset.isPending ? (
                <>
                  <LoaderCircle className="mr-2 size-4 animate-spin" />
                  Guardando...
                </>
              ) : (
                <>
                  <Check className="mr-2 size-4" />
                  Guardar
                </>
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
