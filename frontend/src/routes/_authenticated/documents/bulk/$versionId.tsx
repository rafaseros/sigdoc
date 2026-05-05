import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { z } from "zod";
import { ArrowLeft, FileSpreadsheet } from "lucide-react";

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
      <div className="space-y-5">
        <Skeleton className="h-4 w-32" />
        <div className="flex items-start gap-3.5">
          <Skeleton className="size-12 rounded-xl" />
          <div className="space-y-2">
            <Skeleton className="h-8 w-64" />
            <Skeleton className="h-4 w-96" />
          </div>
        </div>
        <Skeleton className="h-48 w-full rounded-xl" />
      </div>
    );
  }

  if (!template) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-12">
        <p className="text-[var(--fg-3)]">Plantilla no encontrada</p>
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
    <div className="space-y-5">
      {/* Back link */}
      <Link
        to="/templates/$templateId"
        params={{ templateId }}
        className="-ml-1 inline-flex items-center gap-1 text-[12.5px] font-medium text-[var(--fg-3)] transition-colors hover:text-[var(--primary)]"
      >
        <ArrowLeft className="size-3.5" />
        Volver al detalle
      </Link>

      {/* Header */}
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="flex items-start gap-3.5">
          <span className="inline-flex size-12 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-[#d1fae5] to-[#a7f3d0] text-[#065f46]">
            <FileSpreadsheet className="size-5" />
          </span>
          <div className="min-w-0">
            <div className="sd-meta mb-1">Generación masiva</div>
            <h1 className="m-0 text-[22px] font-bold tracking-tight text-[var(--fg-1)]">
              Genere múltiples documentos en bloque
            </h1>
            <p className="mt-1 text-[13px] text-[var(--fg-3)]">
              Desde la plantilla &quot;{template.name}&quot;
              {version && ` (v${version.version})`}
            </p>
          </div>
        </div>

        {template.versions.length > 1 && (
          <div className="flex items-center gap-2">
            <Label className="text-[12.5px] text-[var(--fg-3)]">Versión</Label>
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
              <SelectTrigger className="h-9 w-[140px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {template.versions
                  .sort((a, b) => b.version - a.version)
                  .map((v) => (
                    <SelectItem key={v.id} value={v.id}>
                      v{v.version}
                      {v.version === template.current_version
                        ? " (última)"
                        : ""}
                    </SelectItem>
                  ))}
              </SelectContent>
            </Select>
          </div>
        )}
      </div>

      <BulkGenerateFlow
        templateVersionId={versionId}
        templateName={template.name}
        variableCount={variables.length}
      />
    </div>
  );
}
