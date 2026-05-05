import { createFileRoute } from "@tanstack/react-router";
import {
  History,
  Activity,
  LogIn,
  Sparkles,
  ShieldCheck,
  Lock,
} from "lucide-react";
import { useAuth } from "@/shared/lib/auth";
import { AuditLogTable } from "@/features/audit";
import { useAuditLog } from "@/features/audit/api/queries";

export const Route = createFileRoute("/_authenticated/audit/")({
  beforeLoad: () => {
    // Token presence is already enforced by the _authenticated layout.
    // Role enforcement is handled at the UI level via useAuth().
  },
  component: AuditPage,
});

function AuditPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";

  if (!isAdmin) {
    return (
      <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-[rgba(195,198,215,0.4)] bg-white/60 p-16 text-center">
        <span className="mb-3 inline-flex size-12 items-center justify-center rounded-xl bg-[var(--bg-accent)] text-[var(--primary)]">
          <Lock className="size-5" />
        </span>
        <p className="text-base font-semibold text-[var(--fg-1)]">
          Acceso restringido
        </p>
        <p className="mt-1 text-sm text-[var(--fg-3)]">
          Solo los administradores pueden acceder al registro de auditoría.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-start gap-3.5">
        <span className="inline-flex size-12 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-[#dbe1ff] to-[#b4c5ff] text-[var(--primary)]">
          <History className="size-5" />
        </span>
        <div className="min-w-0">
          <div className="sd-meta mb-1">Seguridad</div>
          <h1 className="m-0 text-[22px] font-bold tracking-tight text-[var(--fg-1)]">
            Auditoría
          </h1>
          <p className="mt-1 text-[13px] text-[var(--fg-3)]">
            Registro inmutable de todas las acciones realizadas en el sistema.
            Las entradas no pueden modificarse ni eliminarse.
          </p>
        </div>
      </div>

      {/* Stat cards (derived from API) */}
      <AuditStats />

      <AuditLogTable />
    </div>
  );
}

function AuditStats() {
  // We use the same hook the table uses (page 1, no filters).
  // React Query dedupes when the table also queries page=1 with no filters.
  const { data } = useAuditLog(1, 50, {});

  const items = data?.items ?? [];
  const total = data?.total ?? 0;

  const now = new Date();
  const startOfToday = new Date(
    now.getFullYear(),
    now.getMonth(),
    now.getDate(),
  );

  const eventsToday = items.filter(
    (e) => new Date(e.created_at) >= startOfToday,
  ).length;

  const logins = items.filter((e) => e.action === "auth.login").length;

  const generations = items.filter(
    (e) =>
      e.action === "document.generate" ||
      e.action === "document.generate_bulk",
  ).length;

  const adminChanges = items.filter(
    (e) =>
      e.action === "user.create" ||
      e.action === "user.update" ||
      e.action === "user.deactivate" ||
      e.action === "auth.change_password",
  ).length;

  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <StatCard
        label="Eventos totales"
        value={total}
        hint={
          eventsToday > 0
            ? `${eventsToday} hoy en esta página`
            : "registros acumulados"
        }
        icon={<Activity className="size-4" />}
      />
      <StatCard
        label="Inicios de sesión"
        value={logins}
        hint="en página actual"
        icon={<LogIn className="size-4" />}
      />
      <StatCard
        label="Generaciones"
        value={generations}
        hint="documentos generados"
        icon={<Sparkles className="size-4" />}
      />
      <StatCard
        label="Cambios admin"
        value={adminChanges}
        hint="usuarios y contraseñas"
        icon={<ShieldCheck className="size-4" />}
      />
    </div>
  );
}

function StatCard({
  label,
  value,
  hint,
  icon,
}: {
  label: string;
  value: number;
  hint: string;
  icon: React.ReactNode;
}) {
  return (
    <div className="relative overflow-hidden rounded-xl bg-white p-4 shadow-[var(--shadow-sm)] ring-1 ring-[rgba(195,198,215,0.30)]">
      <div className="text-xs font-medium uppercase tracking-[0.04em] text-[var(--fg-3)]">
        {label}
      </div>
      <div className="mt-1 text-3xl font-bold tracking-tight text-[var(--fg-1)]">
        {value}
      </div>
      <div className="mt-0.5 text-xs text-[var(--fg-3)]">{hint}</div>
      <div className="absolute right-3 top-3 inline-flex size-8 items-center justify-center rounded-lg bg-[var(--bg-accent)] text-[var(--primary)]">
        {icon}
      </div>
    </div>
  );
}
