import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { ScanText } from "lucide-react";
import { TemplateList, UploadTemplateDialog, TemplateGuideButton, useTemplates } from "@/features/templates";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/shared/lib/auth";
import { canUploadTemplates } from "@/shared/lib/permissions";

export const Route = createFileRoute("/_authenticated/templates/")({
  component: TemplatesPage,
});

function TemplatesPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const { data } = useTemplates();
  const templateCount = data?.total ?? data?.items.length ?? 0;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div>
            <h2 className="text-2xl font-bold tracking-tight text-[var(--fg-1)]">Plantillas</h2>
            <p className="text-sm text-[var(--fg-3)]">
              Gestione sus plantillas de documentos
            </p>
          </div>
          <Badge className="bg-[var(--bg-accent)] text-[var(--primary)] border-0 rounded-full">
            {templateCount} plantillas
          </Badge>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <TemplateGuideButton />
          {canUploadTemplates(user?.role) && (
            <Button
              variant="outline"
              onClick={() => navigate({ to: "/templates/from-example" })}
            >
              <ScanText className="mr-2 size-4" />
              Crear desde ejemplo
            </Button>
          )}
          {canUploadTemplates(user?.role) && <UploadTemplateDialog />}
        </div>
      </div>
      <TemplateList />
    </div>
  );
}
