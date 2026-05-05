import { useState } from "react";
import { Filter, X } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { AuditFilters } from "../api/keys";

const AUDIT_ACTIONS = [
  { value: "template.upload", label: "Subida de plantilla" },
  { value: "template.delete", label: "Eliminación de plantilla" },
  { value: "template.version", label: "Nueva versión" },
  { value: "template.share", label: "Compartir plantilla" },
  { value: "template.unshare", label: "Dejar de compartir" },
  { value: "document.generate", label: "Generación individual" },
  { value: "document.generate_bulk", label: "Generación masiva" },
  { value: "document.delete", label: "Eliminación de documento" },
  { value: "user.create", label: "Creación de usuario" },
  { value: "user.update", label: "Actualización de usuario" },
  { value: "user.deactivate", label: "Desactivación de usuario" },
  { value: "auth.login", label: "Inicio de sesión" },
  { value: "auth.login_failed", label: "Fallo de inicio de sesión" },
  { value: "auth.change_password", label: "Cambio de contraseña" },
];

const QUICK_FILTERS: { value: string | undefined; label: string }[] = [
  { value: undefined, label: "Todas" },
  { value: "auth.login", label: "Sesiones" },
  { value: "document.generate", label: "Generaciones" },
  { value: "template.upload", label: "Subidas" },
  { value: "user.create", label: "Cambios de usuario" },
  { value: "template.delete", label: "Eliminaciones" },
];

interface AuditFiltersProps {
  filters: AuditFilters;
  onChange: (filters: AuditFilters) => void;
}

export function AuditFilters({ filters, onChange }: AuditFiltersProps) {
  const [actorId, setActorId] = useState(filters.actor_id ?? "");
  const [dateFrom, setDateFrom] = useState(filters.date_from ?? "");
  const [dateTo, setDateTo] = useState(filters.date_to ?? "");

  function handleActionChange(value: string) {
    onChange({
      ...filters,
      action: value === "all" ? undefined : value,
    });
  }

  function handleQuickFilter(value: string | undefined) {
    onChange({
      ...filters,
      action: value,
    });
  }

  function handleApply() {
    onChange({
      ...filters,
      actor_id: actorId.trim() || undefined,
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
    });
  }

  function handleClear() {
    setActorId("");
    setDateFrom("");
    setDateTo("");
    onChange({});
  }

  const hasActiveFilters =
    !!filters.action ||
    !!filters.actor_id ||
    !!filters.date_from ||
    !!filters.date_to;

  return (
    <div className="space-y-3">
      {/* Filter card */}
      <div className="rounded-xl bg-white p-4 shadow-[var(--shadow-sm)] ring-1 ring-[rgba(195,198,215,0.30)]">
        <div className="flex flex-wrap items-end gap-3">
          {/* Acción */}
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-[var(--fg-2)]">
              Acción
            </label>
            <Select
              value={filters.action ?? "all"}
              onValueChange={(v) => handleActionChange(v ?? "all")}
            >
              <SelectTrigger className="h-9 w-[210px] text-sm">
                <SelectValue placeholder="Todas las acciones" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todas las acciones</SelectItem>
                {AUDIT_ACTIONS.map((a) => (
                  <SelectItem key={a.value} value={a.value}>
                    {a.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Usuario (actor_id) */}
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-[var(--fg-2)]">
              ID de usuario
            </label>
            <Input
              className="h-9 w-[230px] text-sm"
              placeholder="UUID del usuario..."
              value={actorId}
              onChange={(e) => setActorId(e.target.value)}
            />
          </div>

          {/* Desde */}
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-[var(--fg-2)]">
              Desde
            </label>
            <Input
              type="datetime-local"
              className="h-9 w-[200px] text-sm"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
            />
          </div>

          {/* Hasta */}
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-[var(--fg-2)]">
              Hasta
            </label>
            <Input
              type="datetime-local"
              className="h-9 w-[200px] text-sm"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
            />
          </div>

          <div className="ml-auto flex items-center gap-2">
            {hasActiveFilters && (
              <Button
                size="sm"
                variant="ghost"
                onClick={handleClear}
                className="h-9 text-[var(--fg-2)]"
              >
                <X className="size-3.5" />
                Limpiar
              </Button>
            )}
            <Button
              size="sm"
              onClick={handleApply}
              className="h-9 bg-gradient-to-br from-[#004ac6] to-[#2563eb] font-semibold text-white shadow-[var(--shadow-brand-sm)] hover:shadow-[var(--shadow-brand-md)]"
            >
              <Filter className="size-3.5" />
              Aplicar Filtros
            </Button>
          </div>
        </div>
      </div>

      {/* Quick filter chips */}
      <div className="flex flex-wrap items-center gap-2">
        {QUICK_FILTERS.map((q) => {
          const isActive = (filters.action ?? undefined) === q.value;
          return (
            <button
              key={q.label}
              type="button"
              onClick={() => handleQuickFilter(q.value)}
              className={
                isActive
                  ? "inline-flex items-center rounded-full bg-[var(--bg-accent)] px-3 py-1 text-xs font-semibold text-[var(--primary)] ring-1 ring-[rgba(0,74,198,0.20)]"
                  : "inline-flex items-center rounded-full bg-white px-3 py-1 text-xs font-medium text-[var(--fg-2)] ring-1 ring-[rgba(195,198,215,0.40)] transition-colors hover:bg-[var(--bg-accent)] hover:text-[var(--primary)]"
              }
            >
              {q.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
