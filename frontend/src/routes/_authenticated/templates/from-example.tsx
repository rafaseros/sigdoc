import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { ArrowLeft } from "lucide-react";

import { CreateFromExamplePage } from "@/features/templates/components/CreateFromExamplePage";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/shared/lib/auth";
import { canUploadTemplates } from "@/shared/lib/permissions";

export const Route = createFileRoute("/_authenticated/templates/from-example")(
  {
    component: FromExamplePage,
  },
);

function FromExamplePage() {
  const { user } = useAuth();
  const navigate = useNavigate();

  // Same gate as "Subir Plantilla" — UX mirror only, the backend re-validates.
  if (!canUploadTemplates(user?.role)) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-12">
        <p className="text-[var(--fg-3)]">
          No tiene permisos para crear plantillas.
        </p>
        <Button variant="outline" onClick={() => navigate({ to: "/templates" })}>
          <ArrowLeft />
          Volver a Plantillas
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <Link
        to="/templates"
        className="-ml-1 inline-flex items-center gap-1 text-[12.5px] font-medium text-[var(--fg-3)] transition-colors hover:text-[var(--primary)]"
      >
        <ArrowLeft className="size-3.5" />
        Volver a Plantillas
      </Link>
      <CreateFromExamplePage />
    </div>
  );
}
