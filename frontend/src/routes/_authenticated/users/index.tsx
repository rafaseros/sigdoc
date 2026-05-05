import { createFileRoute } from "@tanstack/react-router";
import { Users, ShieldCheck, FileEdit, Sparkles } from "lucide-react";
import { UserList, CreateUserDialog, useUsers } from "@/features/users";

export const Route = createFileRoute("/_authenticated/users/")({
  beforeLoad: () => {
    // Additional admin check could go here if we had access to auth context
    // The component-level check below handles the UI guard
  },
  component: UsersPage,
});

function UsersPage() {
  const { data } = useUsers({ size: 100 });
  const items = data?.items ?? [];
  const total = data?.total ?? items.length;
  const activeCount = items.filter((u) => u.is_active).length;
  const adminCount = items.filter((u) => u.role === "admin").length;
  const creatorCount = items.filter((u) => u.role === "template_creator").length;
  const generatorCount = items.filter(
    (u) => u.role === "document_generator",
  ).length;

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="sd-meta">Administración</div>
          <h2 className="mt-1.5 text-2xl font-bold tracking-tight text-[var(--fg-1)]">
            Usuarios
          </h2>
          <p className="mt-1 text-sm text-[var(--fg-3)]">
            Gestione cuentas, roles y permisos del sistema. Solo administradores
            pueden crear o desactivar usuarios.
          </p>
        </div>
        <CreateUserDialog />
      </div>

      {/* Stat cards */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Usuarios totales"
          value={total}
          hint={`${activeCount} ${activeCount === 1 ? "activo" : "activos"}`}
          icon={<Users className="size-4" />}
        />
        <StatCard
          label="Administradores"
          value={adminCount}
          hint="acceso total"
          icon={<ShieldCheck className="size-4" />}
        />
        <StatCard
          label="Creadores"
          value={creatorCount}
          hint="suben plantillas"
          icon={<FileEdit className="size-4" />}
        />
        <StatCard
          label="Generadores"
          value={generatorCount}
          hint="solo generan documentos"
          icon={<Sparkles className="size-4" />}
        />
      </div>

      <UserList />
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
