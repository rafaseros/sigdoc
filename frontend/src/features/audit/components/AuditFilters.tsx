import { useState } from "react";
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
    <div className="flex flex-wrap items-end gap-3 rounded-lg border border-[rgba(195,198,215,0.2)] bg-white/60 p-3">
      {/* Acción */}
      <div className="flex flex-col gap-1">
        <label className="text-xs font-medium text-[#434655]">Acción</label>
        <Select
          value={filters.action ?? "all"}
          onValueChange={handleActionChange}
        >
          <SelectTrigger className="h-8 w-[200px] border-[rgba(195,198,215,0.3)] text-sm">
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
      <div className="flex flex-col gap-1">
        <label className="text-xs font-medium text-[#434655]">
          ID de usuario
        </label>
        <Input
          className="h-8 w-[220px] border-[rgba(195,198,215,0.3)] text-sm"
          placeholder="UUID del usuario..."
          value={actorId}
          onChange={(e) => setActorId(e.target.value)}
        />
      </div>

      {/* Desde */}
      <div className="flex flex-col gap-1">
        <label className="text-xs font-medium text-[#434655]">Desde</label>
        <Input
          type="datetime-local"
          className="h-8 w-[190px] border-[rgba(195,198,215,0.3)] text-sm"
          value={dateFrom}
          onChange={(e) => setDateFrom(e.target.value)}
        />
      </div>

      {/* Hasta */}
      <div className="flex flex-col gap-1">
        <label className="text-xs font-medium text-[#434655]">Hasta</label>
        <Input
          type="datetime-local"
          className="h-8 w-[190px] border-[rgba(195,198,215,0.3)] text-sm"
          value={dateTo}
          onChange={(e) => setDateTo(e.target.value)}
        />
      </div>

      {/* Botones */}
      <div className="flex items-center gap-2 pb-0.5">
        <Button
          size="sm"
          onClick={handleApply}
          className="h-8 bg-[#004ac6] hover:bg-[#003da8] text-white"
        >
          Aplicar
        </Button>
        {hasActiveFilters && (
          <Button
            size="sm"
            variant="outline"
            onClick={handleClear}
            className="h-8 border-[rgba(195,198,215,0.3)] hover:bg-[#e6e8ea] text-[#434655]"
          >
            Limpiar
          </Button>
        )}
      </div>
    </div>
  );
}
