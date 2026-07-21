/**
 * PresetsTab.tsx
 *
 * "Datos guardados" tab in TemplateDetail — lists this template's presets
 * (Feature B). Any user with access to the template can see/manage them;
 * the backend enforces the permission, so no ownership gate here.
 */
import { useMemo, useState } from "react";
import { toast } from "sonner";
import { Bookmark, Pencil, Plus, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

import {
  usePresets,
  useDeletePreset,
  type Preset,
} from "@/features/templates/api/presets";
import type { VariableMeta } from "@/features/templates/api/queries";

import { PresetFormDialog } from "./PresetFormDialog";

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString("es-ES", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

interface PresetsTabProps {
  templateId: string;
  /** Current-version variables — filtered to non-computed for the form. */
  variablesMeta: VariableMeta[];
}

export function PresetsTab({ templateId, variablesMeta }: PresetsTabProps) {
  const { data: presets, isLoading } = usePresets(templateId);
  const deletePreset = useDeletePreset(templateId);

  const [formOpen, setFormOpen] = useState(false);
  const [editingPreset, setEditingPreset] = useState<Preset | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);

  const editableVariablesMeta = useMemo(
    () => variablesMeta.filter((m) => !m.computed),
    [variablesMeta],
  );

  function openCreate() {
    setEditingPreset(null);
    setFormOpen(true);
  }

  function openEdit(preset: Preset) {
    setEditingPreset(preset);
    setFormOpen(true);
  }

  async function handleDelete(preset: Preset) {
    try {
      await deletePreset.mutateAsync(preset.id);
      toast.success(`Datos «${preset.name}» eliminados`);
    } catch {
      toast.error("Error al eliminar los datos guardados");
    } finally {
      setConfirmDeleteId(null);
    }
  }

  const list = presets ?? [];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h3 className="m-0 text-lg font-bold tracking-tight text-[var(--fg-1)]">
            Datos guardados
          </h3>
          <p className="mt-1 text-[12.5px] text-[var(--fg-3)]">
            Conjuntos de valores reutilizables para generar documentos
            rápidamente con esta plantilla.
          </p>
        </div>
        <Button
          size="sm"
          onClick={openCreate}
          className="bg-gradient-to-br from-[#004ac6] to-[#2563eb] font-semibold text-white shadow-[var(--shadow-brand-sm)] hover:shadow-[var(--shadow-brand-md)]"
        >
          <Plus className="size-3.5" />
          Nuevo
        </Button>
      </div>

      {isLoading ? (
        <div className="space-y-2.5">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-16 w-full rounded-xl" />
          ))}
        </div>
      ) : list.length === 0 ? (
        <Card className="border-0 bg-white shadow-[var(--shadow-md)]">
          <CardContent className="pt-6">
            <p className="text-[var(--fg-2)]">
              Todavía no hay datos guardados para esta plantilla.
            </p>
            <p className="mt-1 text-sm text-[var(--fg-3)]">
              Usá el botón <strong>Nuevo</strong> arriba para crear el primero.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="flex flex-col gap-2.5">
          {list.map((preset) => {
            const valueCount = Object.keys(preset.values).length;
            const isConfirming = confirmDeleteId === preset.id;
            return (
              <div
                key={preset.id}
                className="flex flex-wrap items-center gap-3.5 rounded-xl bg-white p-4 shadow-[var(--shadow-sm)] ring-1 ring-[rgba(195,198,215,0.30)]"
              >
                <span className="inline-flex size-10 shrink-0 items-center justify-center rounded-[10px] bg-[var(--bg-accent)] text-[var(--primary)]">
                  <Bookmark className="size-4" />
                </span>
                <div className="min-w-[160px] flex-1">
                  <div className="truncate text-sm font-semibold text-[var(--fg-1)]">
                    {preset.name}
                  </div>
                  <div className="mt-0.5 text-[12px] text-[var(--fg-3)]">
                    {valueCount} valor{valueCount === 1 ? "" : "es"} ·{" "}
                    {formatDate(preset.created_at)}
                  </div>
                </div>
                {isConfirming ? (
                  <div className="flex items-center gap-1.5">
                    <Button
                      size="sm"
                      disabled={deletePreset.isPending}
                      onClick={() => handleDelete(preset)}
                      className="bg-[var(--destructive)] font-semibold text-white hover:bg-[#93000a]"
                    >
                      {deletePreset.isPending ? "…" : "Confirmar"}
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setConfirmDeleteId(null)}
                    >
                      No
                    </Button>
                  </div>
                ) : (
                  <div className="flex items-center gap-1.5">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => openEdit(preset)}
                    >
                      <Pencil className="size-3.5" />
                      Editar
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-[var(--destructive)] hover:bg-[#ffdad6]/50 hover:text-[var(--destructive)]"
                      onClick={() => setConfirmDeleteId(preset.id)}
                    >
                      <Trash2 className="size-3.5" />
                      Eliminar
                    </Button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      <PresetFormDialog
        templateId={templateId}
        variablesMeta={editableVariablesMeta}
        preset={editingPreset}
        open={formOpen}
        onOpenChange={setFormOpen}
      />
    </div>
  );
}
