import { useState } from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuditLog, type AuditLogEntry } from "../api/queries";
import { AuditFilters as AuditFiltersComponent } from "./AuditFilters";
import type { AuditFilters } from "../api/keys";

const ACTION_LABELS: Record<string, string> = {
  "template.upload": "Subida de plantilla",
  "template.delete": "Eliminación de plantilla",
  "template.version": "Nueva versión",
  "template.share": "Compartir plantilla",
  "template.unshare": "Dejar de compartir",
  "document.generate": "Generación individual",
  "document.generate_bulk": "Generación masiva",
  "document.delete": "Eliminación de documento",
  "user.create": "Creación de usuario",
  "user.update": "Actualización de usuario",
  "user.deactivate": "Desactivación de usuario",
  "auth.login": "Inicio de sesión",
  "auth.login_failed": "Fallo de inicio de sesión",
  "auth.change_password": "Cambio de contraseña",
};

const ACTION_CATEGORY: Record<string, "template" | "document" | "user" | "auth"> = {
  "template.upload": "template",
  "template.delete": "template",
  "template.version": "template",
  "template.share": "template",
  "template.unshare": "template",
  "document.generate": "document",
  "document.generate_bulk": "document",
  "document.delete": "document",
  "user.create": "user",
  "user.update": "user",
  "user.deactivate": "user",
  "auth.login": "auth",
  "auth.login_failed": "auth",
  "auth.change_password": "auth",
};

function ActionBadge({ action }: { action: string }) {
  const category = ACTION_CATEGORY[action];
  const label = ACTION_LABELS[action] ?? action;

  const styles = {
    template: "bg-[#dbe1ff] text-[#004ac6] border-0 rounded-full",
    document: "bg-[#d1fae5] text-[#059669] border-0 rounded-full",
    user: "bg-[#fef3c7] text-[#d97706] border-0 rounded-full",
    auth: "bg-[#f3f4f6] text-[#6b7280] border-0 rounded-full",
  };

  return (
    <Badge className={styles[category] ?? "border-0 rounded-full"}>
      {label}
    </Badge>
  );
}

function formatDetails(details: Record<string, unknown> | null): string {
  if (!details) return "—";
  const entries = Object.entries(details);
  if (entries.length === 0) return "—";
  return entries
    .slice(0, 3)
    .map(([k, v]) => `${k}: ${String(v)}`)
    .join(", ");
}

function formatDate(dateString: string): string {
  return new Date(dateString).toLocaleDateString("es-ES", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function AuditRow({ entry }: { entry: AuditLogEntry }) {
  const detailsSummary = formatDetails(entry.details);

  return (
    <TableRow className="border-b border-[rgba(195,198,215,0.1)] transition-colors hover:bg-[#e6e8ea]/50">
      <TableCell className="text-[#434655] text-xs whitespace-nowrap">
        {formatDate(entry.created_at)}
      </TableCell>
      <TableCell className="text-[#191c1e] font-mono text-xs">
        {entry.actor_id ? (
          <span title={entry.actor_id}>
            {entry.actor_id.slice(0, 8)}...
          </span>
        ) : (
          <span className="text-[#9ca3af]">—</span>
        )}
      </TableCell>
      <TableCell>
        <ActionBadge action={entry.action} />
      </TableCell>
      <TableCell className="text-[#434655] text-sm">
        {entry.resource_type ?? "—"}
      </TableCell>
      <TableCell
        className="text-[#434655] text-xs max-w-[240px] truncate"
        title={detailsSummary !== "—" ? detailsSummary : undefined}
      >
        {detailsSummary}
      </TableCell>
      <TableCell className="text-[#434655] text-xs font-mono">
        {entry.ip_address ?? "—"}
      </TableCell>
    </TableRow>
  );
}

export function AuditLogTable() {
  const [page, setPage] = useState(1);
  const size = 50;
  const [filters, setFilters] = useState<AuditFilters>({});

  const { data, isLoading, isError, error } = useAuditLog(page, size, filters);

  const totalPages = data ? Math.ceil(data.total / size) : 0;

  function handleFiltersChange(newFilters: AuditFilters) {
    setFilters(newFilters);
    setPage(1);
  }

  return (
    <div className="space-y-4">
      <AuditFiltersComponent filters={filters} onChange={handleFiltersChange} />

      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </div>
      ) : isError ? (
        <div className="rounded-lg border border-destructive/50 bg-destructive/5 p-4 text-sm text-destructive">
          Error al cargar el registro de auditoría:{" "}
          {error?.message ?? "Error desconocido"}
        </div>
      ) : !data?.items.length ? (
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-[rgba(195,198,215,0.3)] bg-white/50 p-12 text-center">
          <p className="text-sm text-[#434655]">
            No hay entradas de auditoría para los filtros seleccionados.
          </p>
        </div>
      ) : (
        <>
          <div className="rounded-lg bg-white shadow-[0_12px_32px_rgba(25,28,30,0.06)] overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow className="bg-[#eceef0] border-b border-[rgba(195,198,215,0.2)] hover:bg-[#eceef0]">
                  <TableHead className="font-semibold text-[#191c1e]">
                    Fecha
                  </TableHead>
                  <TableHead className="font-semibold text-[#191c1e]">
                    Usuario
                  </TableHead>
                  <TableHead className="font-semibold text-[#191c1e]">
                    Acción
                  </TableHead>
                  <TableHead className="font-semibold text-[#191c1e]">
                    Recurso
                  </TableHead>
                  <TableHead className="font-semibold text-[#191c1e]">
                    Detalles
                  </TableHead>
                  <TableHead className="font-semibold text-[#191c1e]">
                    IP
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.items.map((entry) => (
                  <AuditRow key={entry.id} entry={entry} />
                ))}
              </TableBody>
            </Table>
          </div>

          {totalPages > 1 && (
            <div className="flex items-center justify-between">
              <p className="text-sm text-[#434655]">
                Mostrando {data.items.length} de {data.total} entradas
              </p>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  className="border-[rgba(195,198,215,0.3)] hover:bg-[#e6e8ea] text-[#434655]"
                >
                  Anterior
                </Button>
                <span className="text-sm text-[#434655]">
                  Página {page} de {totalPages}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => p + 1)}
                  className="border-[rgba(195,198,215,0.3)] hover:bg-[#e6e8ea] text-[#434655]"
                >
                  Siguiente
                </Button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
