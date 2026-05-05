import { createFileRoute } from "@tanstack/react-router";
import { TemplateList, UploadTemplateDialog, TemplateGuideButton, useTemplates } from "@/features/templates";
import { Badge } from "@/components/ui/badge";
import { useAuth } from "@/shared/lib/auth";
import { canUploadTemplates } from "@/shared/lib/permissions";

export const Route = createFileRoute("/_authenticated/templates/")({
  component: TemplatesPage,
});

function TemplatesPage() {
  const { user } = useAuth();
  const { data } = useTemplates();
  const templateCount = data?.total ?? data?.items.length ?? 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div>
            <h2 className="text-2xl font-bold">Plantillas</h2>
            <p className="text-muted-foreground">
              Gestione sus plantillas de documentos
            </p>
          </div>
          <Badge className="bg-[#dbe1ff] text-[#004ac6] border-0 rounded-full">
            {templateCount} plantillas
          </Badge>
        </div>
        <div className="flex items-center gap-2">
          <TemplateGuideButton />
          {canUploadTemplates(user?.role) && <UploadTemplateDialog />}
        </div>
      </div>
      <TemplateList />
    </div>
  );
}
