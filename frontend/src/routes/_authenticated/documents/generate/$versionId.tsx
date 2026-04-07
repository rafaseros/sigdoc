import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { z } from "zod";

import { useTemplate } from "@/features/templates/api/queries";
import { DynamicForm } from "@/features/documents/components/DynamicForm";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { ArrowLeft } from "lucide-react";

const searchSchema = z.object({
  templateId: z.string(),
});

export const Route = createFileRoute(
  "/_authenticated/documents/generate/$versionId",
)({
  validateSearch: searchSchema,
  component: GeneratePage,
});

function GeneratePage() {
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
        <Skeleton className="h-64 w-full" />
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

  const currentVersion = template.versions.find((v) => v.id === versionId);
  const variables = currentVersion?.variables ?? template.variables;
  const variablesMeta = currentVersion?.variables_meta ?? [];

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
          <h1 className="text-2xl font-bold">Generar Documento</h1>
          <p className="text-muted-foreground">
            Desde la plantilla "{template.name}"
            {currentVersion && ` (v${currentVersion.version})`}
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
                  to: "/documents/generate/$versionId",
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

      {variables.length === 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>Sin Variables</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-muted-foreground">
              Esta plantilla no tiene variables. El documento se generará
              tal cual.
            </p>
            <DynamicForm
              templateVersionId={versionId}
              variables={[]}
              variablesMeta={[]}
              templateName={template.name}
            />
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>Complete las Variables</CardTitle>
          </CardHeader>
          <CardContent>
            <DynamicForm
              templateVersionId={versionId}
              variables={variables}
              variablesMeta={variablesMeta}
              templateName={template.name}
            />
          </CardContent>
        </Card>
      )}
    </div>
  );
}
