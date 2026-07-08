/**
 * PresetFormDialog.tsx
 *
 * Create/edit dialog for a template's saved data ("Datos guardados" tab).
 * `preset == null` renders the create form (empty fields); passing a
 * `preset` renders the edit form, prefilled from `preset.values`. Both
 * modes render one <Input> per current-version, non-computed variable —
 * the caller (`PresetsTab`) is responsible for filtering out computed ones.
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

import {
  useCreatePreset,
  useUpdatePreset,
  type Preset,
} from "@/features/templates/api/presets";
import type { VariableMeta } from "@/features/templates/api/queries";

interface PresetFormDialogProps {
  templateId: string;
  /** Current-version, non-computed variables — one <Input> is rendered per entry. */
  variablesMeta: VariableMeta[];
  /** `null` = create a new preset; otherwise edit this one. */
  preset: Preset | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function extractErrorDetail(err: unknown): string | null {
  if (
    err &&
    typeof err === "object" &&
    "response" in err &&
    (err as { response?: { data?: { detail?: string } } }).response?.data
      ?.detail
  ) {
    return (err as { response: { data: { detail: string } } }).response.data
      .detail;
  }
  return null;
}

export function PresetFormDialog({
  templateId,
  variablesMeta,
  preset,
  open,
  onOpenChange,
}: PresetFormDialogProps) {
  const isEdit = preset != null;
  const [name, setName] = useState("");
  const [fieldValues, setFieldValues] = useState<Record<string, string>>({});

  // Re-sync the draft fields every time the dialog (re)opens — either blank
  // (create) or prefilled from the target preset (edit).
  useEffect(() => {
    if (!open) return;
    setName(preset?.name ?? "");
    const initial: Record<string, string> = {};
    for (const m of variablesMeta) {
      initial[m.name] = preset?.values?.[m.name] ?? "";
    }
    setFieldValues(initial);
    // variablesMeta is derived from the template's current version and is
    // stable for the lifetime of a single dialog open — only `open`/`preset`
    // should re-trigger the reset.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, preset]);

  const createPreset = useCreatePreset(templateId);
  const updatePreset = useUpdatePreset(templateId);
  const isPending = createPreset.isPending || updatePreset.isPending;

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmedName = name.trim();
    if (!trimmedName) return;

    const values: Record<string, string> = {};
    for (const [key, value] of Object.entries(fieldValues)) {
      if (value.trim().length > 0) values[key] = value;
    }

    if (isEdit && preset) {
      updatePreset.mutate(
        { presetId: preset.id, name: trimmedName, values },
        {
          onSuccess: () => {
            toast.success("Datos guardados actualizados");
            onOpenChange(false);
          },
          onError: (err: unknown) => {
            toast.error(
              extractErrorDetail(err) ||
                "Error al actualizar los datos guardados",
            );
          },
        },
      );
    } else {
      createPreset.mutate(
        { name: trimmedName, values },
        {
          onSuccess: () => {
            toast.success("Datos guardados creados");
            onOpenChange(false);
          },
          onError: (err: unknown) => {
            toast.error(
              extractErrorDetail(err) || "Error al crear los datos guardados",
            );
          },
        },
      );
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-lg">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>
              {isEdit ? "Editar datos guardados" : "Nuevos datos guardados"}
            </DialogTitle>
            <DialogDescription>
              {isEdit
                ? "Actualice el nombre o los valores de este conjunto."
                : "Cree un conjunto de valores reutilizable para generar documentos con esta plantilla."}
            </DialogDescription>
          </DialogHeader>

          <div className="flex flex-col gap-4 py-4">
            <div className="grid gap-1.5">
              <Label
                htmlFor="preset-form-name"
                className="text-[12.5px] font-medium text-[var(--fg-2)]"
              >
                Nombre
              </Label>
              <Input
                id="preset-form-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="ej. Cliente Acme"
                required
                autoFocus
              />
            </div>

            {variablesMeta.length === 0 ? (
              <p className="text-[12.5px] text-[var(--fg-3)]">
                Esta plantilla no tiene variables editables.
              </p>
            ) : (
              <div className="grid gap-3">
                {variablesMeta.map((m) => (
                  <div key={m.name} className="grid gap-1.5">
                    <Label
                      htmlFor={`preset-field-${m.name}`}
                      className="text-[12.5px] font-medium text-[var(--fg-2)]"
                    >
                      {m.name}
                    </Label>
                    <Input
                      id={`preset-field-${m.name}`}
                      value={fieldValues[m.name] ?? ""}
                      onChange={(e) =>
                        setFieldValues((prev) => ({
                          ...prev,
                          [m.name]: e.target.value,
                        }))
                      }
                      placeholder={m.help_text ?? m.name}
                    />
                  </div>
                ))}
              </div>
            )}
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
              disabled={!name.trim() || isPending}
              className="bg-gradient-to-br from-[#004ac6] to-[#2563eb] font-semibold text-white shadow-[var(--shadow-brand-sm)] hover:shadow-[var(--shadow-brand-md)] disabled:opacity-60"
            >
              {isPending ? (
                <>
                  <LoaderCircle className="mr-2 size-4 animate-spin" />
                  Guardando...
                </>
              ) : (
                <>
                  <Check className="mr-2 size-4" />
                  {isEdit ? "Guardar cambios" : "Crear"}
                </>
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
