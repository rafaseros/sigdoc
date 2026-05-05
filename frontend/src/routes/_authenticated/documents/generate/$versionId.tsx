import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { z } from "zod";

import { useTemplate, useTemplateStructure } from "@/features/templates/api/queries";
import { DynamicForm } from "@/features/documents/components/DynamicForm";
import { FullDocumentEditor } from "@/features/documents/components/FullDocumentEditor";
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
import { ArrowLeft, FileText } from "lucide-react";

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
  const { data: structure, isLoading: structureLoading, isError: structureError } =
    useTemplateStructure(templateId, versionId);

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
        <Skeleton className="h-64 w-full rounded-xl" />
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

  const currentVersion = template.versions.find((v) => v.id === versionId);
  const variables = currentVersion?.variables ?? template.variables;
  const variablesMeta = currentVersion?.variables_meta ?? [];

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
          <span className="inline-flex size-12 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-[#dbe1ff] to-[#b4c5ff] text-[var(--primary)]">
            <FileText className="size-5" />
          </span>
          <div className="min-w-0">
            <div className="sd-meta mb-1">Generación individual</div>
            <h1 className="m-0 text-[22px] font-bold tracking-tight text-[var(--fg-1)]">
              Generar Documento
            </h1>
            <p className="mt-1 text-[13px] text-[var(--fg-3)]">
              Desde la plantilla &quot;{template.name}&quot;
              {currentVersion && ` (v${currentVersion.version})`}
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
                    to: "/documents/generate/$versionId",
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

      {variables.length === 0 ? (
        <div className="rounded-xl bg-white p-6 shadow-[var(--shadow-sm)] ring-1 ring-[rgba(195,198,215,0.30)]">
          <h3 className="m-0 text-base font-bold tracking-tight text-[var(--fg-1)]">
            Sin Variables
          </h3>
          <p className="mt-1.5 mb-4 text-[13px] text-[var(--fg-3)]">
            Esta plantilla no tiene variables. El documento se generará tal
            cual.
          </p>
          <DynamicForm
            templateVersionId={versionId}
            variables={[]}
            variablesMeta={[]}
            templateName={template.name}
          />
        </div>
      ) : structureLoading ? (
        <Skeleton className="h-96 w-full rounded-xl" />
      ) : structure && !structureError ? (
        <FullDocumentEditor
          templateVersionId={versionId}
          templateName={template.name}
          variablesMeta={variablesMeta}
          structure={structure}
        />
      ) : (
        // Structure failed to load — fall back to the legacy variable-form
        // editor so the user can still generate the document.
        <DynamicForm
          templateVersionId={versionId}
          variables={variables}
          variablesMeta={variablesMeta}
          templateName={template.name}
        />
      )}
    </div>
  );
}
