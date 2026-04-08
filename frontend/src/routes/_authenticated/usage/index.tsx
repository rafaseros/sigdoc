import { createFileRoute } from "@tanstack/react-router";
import { useAuth } from "@/shared/lib/auth";
import { UsageWidget, TenantUsageTable } from "@/features/usage";

export const Route = createFileRoute("/_authenticated/usage/")({
  component: UsagePage,
});

function UsagePage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";

  return (
    <div className="space-y-8">
      {/* Encabezado */}
      <div>
        <h2 className="text-2xl font-bold text-[#191c1e]">Uso</h2>
        <p className="text-[#434655]">
          Estadísticas de generación de documentos del mes actual
        </p>
      </div>

      {/* Widget personal */}
      <section className="space-y-3">
        <h3 className="text-base font-semibold text-[#191c1e]">Mi actividad</h3>
        <UsageWidget />
      </section>

      {/* Sección admin — uso por tenant */}
      {isAdmin && (
        <section className="space-y-3">
          <div>
            <h3 className="text-base font-semibold text-[#191c1e]">
              Uso del tenant
            </h3>
            <p className="text-sm text-[#434655]">
              Desglose por usuario para el mes actual
            </p>
          </div>
          <TenantUsageTable />
        </section>
      )}
    </div>
  );
}
