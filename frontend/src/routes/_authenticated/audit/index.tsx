import { createFileRoute } from "@tanstack/react-router";
import { useAuth } from "@/shared/lib/auth";
import { AuditLogTable } from "@/features/audit";

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
      <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-[rgba(195,198,215,0.3)] bg-white/50 p-16 text-center">
        <p className="text-[#191c1e] font-semibold">Acceso restringido</p>
        <p className="mt-1 text-sm text-[#434655]">
          Solo los administradores pueden acceder al registro de auditoría.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-[#191c1e]">Auditoría</h2>
        <p className="text-[#434655]">
          Registro inmutable de todas las acciones realizadas en el sistema
        </p>
      </div>
      <AuditLogTable />
    </div>
  );
}
