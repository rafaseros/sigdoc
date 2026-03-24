import { createFileRoute } from "@tanstack/react-router";
import { TemplateList, UploadTemplateDialog, TemplateGuideButton, TemplateGuideBanner } from "@/features/templates";

export const Route = createFileRoute("/_authenticated/templates/")({
  component: TemplatesPage,
});

function TemplatesPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Plantillas</h2>
          <p className="text-muted-foreground">
            Gestione sus plantillas de documentos
          </p>
        </div>
        <div className="flex items-center gap-2">
          <TemplateGuideButton />
          <UploadTemplateDialog />
        </div>
      </div>
      <TemplateGuideBanner />
      <TemplateList />
    </div>
  );
}
