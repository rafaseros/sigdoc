import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { z } from "zod";
import { ArrowLeft } from "lucide-react";

import { useTemplate } from "@/features/templates/api/queries";
import { BulkGenerateFlow } from "@/features/documents/components/BulkGenerateFlow";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Label } from "@/components/ui/label";

const searchSchema = z.object({
  templateId: z.string(),
});

export const Route = createFileRoute(
  "/_authenticated/documents/bulk/$versionId",
)({
  validateSearch: searchSchema,
  component: BulkGeneratePage,
});

function BulkGeneratePage() {
  const { versionId } = Route.useParams();
  const { templateId } = Route.useSearch();
  const navigate = useNavigate();
  const { data: template, isLoading } = useTemplate(templateId);

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Skeleton className="h-10 w-10" />
          <div className="space-y-2">
            <Skeleton className="h-8 w-64" />
            <Skeleton className="h-4 w-96" />
          </div>
        </div>
        <Skeleton className="h-48 w-full" />
      </div>
    );
  }

  if (!template) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-12">
        <p className="text-muted-foreground">Plantilla no encontrada</p>
        <Button
          variant="outline"
          onClick={() => navigate({ to: "/templates" })}
        >
          <ArrowLeft />
          Volver a Plantillas
        </Button>
      </div>
    );
  }

  const version = template.versions.find((v) => v.id === versionId);
  const variables = version?.variables ?? template.variables;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Button
          variant="ghost"
          size="icon"
          onClick={() =>
            navigate({
              to: "/templates/$templateId",
              params: { templateId },
            })
          }
        >
          <ArrowLeft />
        </Button>
        <div>
          <h1 className="text-2xl font-bold">Generación Masiva</h1>
          <p className="text-muted-foreground">
            Desde la plantilla "{template.name}"
            {version && ` (v${version.version})`}
          </p>
        </div>
      </div>

      {template.versions.length > 1 && (
        <div className="flex items-center gap-3">
          <Label>Versión</Label>
          <Select
            value={versionId}
            onValueChange={(value) => {
              if (value && value !== versionId) {
                navigate({
                  to: "/documents/bulk/$versionId",
                  params: { versionId: value as string },
                  search: { templateId },
                });
              }
            }}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {template.versions
                .sort((a, b) => b.version - a.version)
                .map((v) => (
                  <SelectItem key={v.id} value={v.id}>
                    v{v.version}
                    {v.version === template.current_version ? " (última)" : ""}
                  </SelectItem>
                ))}
            </SelectContent>
          </Select>
        </div>
      )}

      <BulkGenerateFlow
        templateVersionId={versionId}
        templateName={template.name}
        variableCount={variables.length}
      />
    </div>
  );
}
