import { useState } from "react";
import {
  Upload,
  Trash,
  FileUp,
  Share2,
  XCircle,
  Sparkles,
  FileX,
  UserPlus,
  UserCog,
  UserX,
  LogIn,
  ShieldAlert,
  KeyRound,
  Activity,
  CircleAlert,
} from "lucide-react";
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

type ActionTone = "template" | "document" | "user" | "auth" | "danger";

interface ActionMeta {
  tone: ActionTone;
  Icon: React.ComponentType<{ className?: string }>;
}

const ACTION_META: Record<string, ActionMeta> = {
  "template.upload": { tone: "template", Icon: Upload },
  "template.delete": { tone: "danger", Icon: Trash },
  "template.version": { tone: "template", Icon: FileUp },
  "template.share": { tone: "template", Icon: Share2 },
  "template.unshare": { tone: "template", Icon: XCircle },
  "document.generate": { tone: "document", Icon: Sparkles },
  "document.generate_bulk": { tone: "document", Icon: Sparkles },
  "document.delete": { tone: "danger", Icon: FileX },
  "user.create": { tone: "user", Icon: UserPlus },
  "user.update": { tone: "user", Icon: UserCog },
  "user.deactivate": { tone: "danger", Icon: UserX },
  "auth.login": { tone: "auth", Icon: LogIn },
  "auth.login_failed": { tone: "danger", Icon: ShieldAlert },
  "auth.change_password": { tone: "auth", Icon: KeyRound },
};

const TONE_STYLES: Record<ActionTone, { wrap: string; pill: string }> = {
  template: {
    wrap: "bg-[#dbe1ff] text-[#004ac6]",
    pill: "bg-[#dbe1ff] text-[#004ac6]",
  },
  document: {
    wrap: "bg-[#d1fae5] text-[#059669]",
    pill: "bg-[#d1fae5] text-[#059669]",
  },
  user: {
    wrap: "bg-[#fef3c7] text-[#b45309]",
    pill: "bg-[#fef3c7] text-[#b45309]",
  },
  auth: {
    wrap: "bg-[#e0e7ff] text-[#4338ca]",
    pill: "bg-[#e0e7ff] text-[#4338ca]",
  },
  danger: {
    wrap: "bg-[#ffdad6] text-[#93000a]",
    pill: "bg-[#ffdad6] text-[#93000a]",
  },
};

function getActionMeta(action: string): ActionMeta {
  return ACTION_META[action] ?? { tone: "auth", Icon: Activity };
}

function formatDetails(details: Record<string, unknown> | null): string {
  if (!details) return "";
  const entries = Object.entries(details);
  if (entries.length === 0) return "";
  return entries
    .slice(0, 3)
    .map(([k, v]) => `${k}: ${String(v)}`)
    .join(" · ");
}

function formatTime(dateString: string): string {
  return new Date(dateString).toLocaleTimeString("es-ES", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatDateLong(dateString: string): string {
  return new Date(dateString).toLocaleDateString("es-ES", {
    weekday: "long",
    day: "numeric",
    month: "long",
  });
}

type DayBucket = "today" | "this-week" | "earlier";

const BUCKET_LABELS: Record<DayBucket, string> = {
  today: "Hoy",
  "this-week": "Esta semana",
  earlier: "Anteriores",
};

function getBucket(dateString: string, now: Date): DayBucket {
  const d = new Date(dateString);
  const startOfToday = new Date(
    now.getFullYear(),
    now.getMonth(),
    now.getDate(),
  );
  if (d >= startOfToday) return "today";

  // Start of this week (Monday)
  const dayOfWeek = (now.getDay() + 6) % 7; // 0 = Monday
  const startOfWeek = new Date(startOfToday);
  startOfWeek.setDate(startOfToday.getDate() - dayOfWeek);
  if (d >= startOfWeek) return "this-week";

  return "earlier";
}

function groupEntries(
  items: AuditLogEntry[],
): Array<{ bucket: DayBucket; entries: AuditLogEntry[] }> {
  const now = new Date();
  const buckets: Record<DayBucket, AuditLogEntry[]> = {
    today: [],
    "this-week": [],
    earlier: [],
  };
  for (const entry of items) {
    buckets[getBucket(entry.created_at, now)].push(entry);
  }
  return (["today", "this-week", "earlier"] as DayBucket[])
    .map((bucket) => ({ bucket, entries: buckets[bucket] }))
    .filter((g) => g.entries.length > 0);
}

function TimelineRow({ entry }: { entry: AuditLogEntry }) {
  const meta = getActionMeta(entry.action);
  const label = ACTION_LABELS[entry.action] ?? entry.action;
  const tone = TONE_STYLES[meta.tone];
  const Icon = meta.Icon;
  const detailsSummary = formatDetails(entry.details);

  const actorLabel = entry.actor_email
    ? entry.actor_email.split("@")[0]
    : "Sistema";

  return (
    <div className="grid grid-cols-[88px_1fr_auto] items-start gap-4 px-4 py-3.5 transition-colors hover:bg-[var(--bg-muted)]/50 sm:grid-cols-[110px_1fr_180px_120px] sm:px-5">
      {/* Time */}
      <div className="text-xs font-medium tabular-nums text-[var(--fg-3)]">
        {formatTime(entry.created_at)}
      </div>

      {/* Action + details */}
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <span
            className={`inline-flex size-7 shrink-0 items-center justify-center rounded-lg ${tone.wrap}`}
          >
            <Icon className="size-3.5" />
          </span>
          <span
            className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold ${tone.pill}`}
          >
            {label}
          </span>
        </div>
        {detailsSummary && (
          <div className="mt-1.5 truncate text-[12px] text-[var(--fg-2)]">
            {detailsSummary}
          </div>
        )}
        {entry.resource_type && (
          <div className="mt-0.5 font-mono text-[11px] text-[var(--fg-3)]">
            recurso: {entry.resource_type}
            {entry.resource_id ? ` · ${entry.resource_id.slice(0, 8)}` : ""}
          </div>
        )}
      </div>

      {/* Actor */}
      <div className="hidden items-center gap-2 sm:flex">
        <span className="inline-flex size-7 items-center justify-center rounded-full bg-[var(--bg-accent)] text-[11px] font-semibold uppercase text-[var(--primary)]">
          {actorLabel.slice(0, 2)}
        </span>
        <span
          className="truncate text-xs font-medium text-[var(--fg-2)]"
          title={entry.actor_email ?? entry.actor_id ?? "Sistema"}
        >
          {actorLabel}
        </span>
      </div>

      {/* IP */}
      <div className="hidden text-right font-mono text-[11px] text-[var(--fg-3)] sm:block">
        {entry.ip_address ?? "—"}
      </div>
    </div>
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

  const groups = data ? groupEntries(data.items) : [];

  return (
    <div className="space-y-5">
      <AuditFiltersComponent filters={filters} onChange={handleFiltersChange} />

      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-16 w-full rounded-xl" />
          ))}
        </div>
      ) : isError ? (
        <div className="flex items-start gap-3 rounded-xl border border-destructive/40 bg-destructive/5 p-4 text-sm text-destructive">
          <CircleAlert className="size-4 shrink-0" />
          <div>
            Error al cargar el registro de auditoría:{" "}
            {error?.message ?? "Error desconocido"}
          </div>
        </div>
      ) : !data?.items.length ? (
        <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-[rgba(195,198,215,0.4)] bg-white/60 p-12 text-center">
          <Activity className="mb-3 size-8 text-[var(--fg-3)]" />
          <p className="text-sm font-medium text-[var(--fg-1)]">
            No hay entradas de auditoría
          </p>
          <p className="mt-1 text-xs text-[var(--fg-3)]">
            No encontramos eventos para los filtros seleccionados.
          </p>
        </div>
      ) : (
        <>
          <div className="space-y-6">
            {groups.map(({ bucket, entries }) => {
              const newestDate = entries[0]?.created_at;
              return (
                <div key={bucket}>
                  <div className="mb-2.5 flex items-baseline gap-2 px-1">
                    <h3 className="sd-meta">{BUCKET_LABELS[bucket]}</h3>
                    <span className="text-[11px] text-[var(--fg-3)]">
                      · {entries.length}{" "}
                      {entries.length === 1 ? "evento" : "eventos"}
                    </span>
                    {bucket !== "today" && newestDate && (
                      <span className="ml-auto text-[11px] capitalize text-[var(--fg-3)]">
                        {formatDateLong(newestDate)}
                      </span>
                    )}
                  </div>
                  <div className="overflow-hidden rounded-xl bg-white shadow-[var(--shadow-sm)] ring-1 ring-[rgba(195,198,215,0.30)]">
                    {entries.map((entry, idx) => (
                      <div
                        key={entry.id}
                        className={
                          idx === 0
                            ? ""
                            : "border-t border-[rgba(195,198,215,0.18)]"
                        }
                      >
                        <TimelineRow entry={entry} />
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>

          {totalPages > 1 && (
            <div className="flex items-center justify-between rounded-xl bg-white px-4 py-3 shadow-[var(--shadow-sm)] ring-1 ring-[rgba(195,198,215,0.30)]">
              <p className="text-xs text-[var(--fg-3)]">
                Mostrando {data.items.length} de {data.total} entradas
              </p>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                >
                  Anterior
                </Button>
                <span className="text-xs font-medium text-[var(--fg-2)]">
                  Página {page} de {totalPages}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => p + 1)}
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
