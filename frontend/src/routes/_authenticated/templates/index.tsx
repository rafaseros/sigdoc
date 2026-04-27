import { createFileRoute } from "@tanstack/react-router";
import { TemplateList, UploadTemplateDialog, TemplateGuideButton, TemplateGuideBanner } from "@/features/templates";
import { Badge } from "@/components/ui/badge";
import { useTenantTier } from "@/features/subscription/api/queries";
import { useAuth } from "@/shared/lib/auth";
import { canUploadTemplates } from "@/shared/lib/permissions";

export const Route = createFileRoute("/_authenticated/templates/")({
  component: TemplatesPage,
});

function TemplatesPage() {
  const { user } = useAuth();
  const { data: tierData } = useTenantTier();
  const templateUsage = tierData?.usage.templates ?? null;

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
          {templateUsage !== null && (
            <Badge
              className={
                templateUsage.near_limit
                  ? "bg-[#ffdad6] text-[#ba1a1a] border-0 rounded-full"
                  : "bg-[#dbe1ff] text-[#004ac6] border-0 rounded-full"
              }
            >
              {templateUsage.used}
              {templateUsage.limit !== null ? ` / ${templateUsage.limit}` : ""} plantillas
            </Badge>
          )}
        </div>
        <div className="flex items-center gap-2">
          <TemplateGuideButton />
          {canUploadTemplates(user?.role) && <UploadTemplateDialog />}
        </div>
      </div>
      <TemplateGuideBanner />
      <TemplateList />
    </div>
  );
}
