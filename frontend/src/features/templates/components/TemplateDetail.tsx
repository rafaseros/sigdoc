import { Fragment, useState, useCallback } from "react";
import { useNavigate } from "@tanstack/react-router";
import { toast } from "sonner";
import { useDropzone } from "react-dropzone";
import {
  ArrowLeft,
  FileText,
  Files,
  Trash2,
  Variable,
  Info,
  Clock,
  Upload,
  Share2,
} from "lucide-react";

import {
  useTemplate,
  useDeleteTemplate,
  useUploadNewVersion,
} from "@/features/templates/api";
import type { VariableMeta, VariableType } from "@/features/templates/api/queries";
import {
  useUpdateVariableTypes,
  type VariableTypeOverrideInput,
} from "@/features/templates/api/mutations";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

import { TemplateDetailSkeleton } from "./TemplateDetailSkeleton";
import { DocumentsTab } from "./DocumentsTab";
import { ShareTemplateDialog } from "./ShareTemplateDialog";
import { SharesTab } from "./SharesTab";

function formatFileSize(bytes: number): string {
  if (bytes === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${(bytes / Math.pow(1024, i)).toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

// ---------------------------------------------------------------------------
// Variables Tab
// ---------------------------------------------------------------------------

const TYPE_LABELS: Record<VariableType, string> = {
  text: "Texto",
  integer: "Número entero",
  decimal: "Número decimal",
  select: "Selección",
};

interface VariableRowState {
  type: VariableType;
  optionsText: string;
  helpText: string;
}

function initRow(meta: VariableMeta): VariableRowState {
  return {
    type: meta.type ?? "text",
    optionsText: meta.options ? meta.options.join("\n") : "",
    helpText: meta.help_text ?? "",
  };
}

function optionsTextToList(raw: string): string[] {
  return raw
    .split("\n")
    .map((l) => l.trim())
    .filter((l) => l.length > 0);
}

interface VariablesTabProps {
  templateId: string;
  versionId: string;
  variablesMeta: VariableMeta[];
  isOwner: boolean;
}

/**
 * Render a paragraph context with all `{{ varName }}` occurrences highlighted —
 * helps the owner spot exactly where a given variable shows up in the document.
 * Other placeholders in the same paragraph stay as plain text.
 */
function HighlightedContext({ ctx, varName }: { ctx: string; varName: string }) {
  // Variable names are \w-only (Jinja2 constraint), so no regex escaping needed,
  // but we escape defensively in case future names break that assumption.
  const escaped = varName.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const pattern = new RegExp(`\\{\\{\\s*${escaped}\\s*\\}\\}`, "g");
  const parts = ctx.split(pattern);
  const matches = ctx.match(pattern) ?? [];
  return (
    <>
      {parts.map((part, i) => (
        <Fragment key={i}>
          {part}
          {i < matches.length && (
            <span className="bg-yellow-200 text-yellow-900 px-1 rounded font-semibold not-italic mx-0.5">
              {matches[i]}
            </span>
          )}
        </Fragment>
      ))}
    </>
  );
}

function VariablesTab({ templateId, versionId, variablesMeta, isOwner }: VariablesTabProps) {
  const [rows, setRows] = useState<Record<string, VariableRowState>>(() =>
    Object.fromEntries(variablesMeta.map((m) => [m.name, initRow(m)]))
  );
  const [isDirty, setIsDirty] = useState(false);

  const updateMutation = useUpdateVariableTypes(templateId, versionId);

  function setRowType(name: string, type: VariableType) {
    setRows((prev) => ({ ...prev, [name]: { ...prev[name], type } }));
    setIsDirty(true);
  }

  function setRowOptions(name: string, optionsText: string) {
    setRows((prev) => ({ ...prev, [name]: { ...prev[name], optionsText } }));
    setIsDirty(true);
  }

  function setRowHelpText(name: string, helpText: string) {
    setRows((prev) => ({ ...prev, [name]: { ...prev[name], helpText } }));
    setIsDirty(true);
  }

  function handleDiscard() {
    setRows(Object.fromEntries(variablesMeta.map((m) => [m.name, initRow(m)])));
    setIsDirty(false);
  }

  function handleSave() {
    const overrides: VariableTypeOverrideInput[] = variablesMeta.map((m) => {
      const row = rows[m.name] ?? initRow(m);
      const options = row.type === "select" ? optionsTextToList(row.optionsText) : null;
      return {
        name: m.name,
        type: row.type,
        options,
        help_text: row.helpText.trim() !== "" ? row.helpText.trim() : null,
      };
    });

    for (const o of overrides) {
      if (o.type === "select" && (!o.options || o.options.length === 0)) {
        toast.error(
          `La variable "${o.name}" es de tipo Selección pero no tiene opciones. Ingrese al menos una opción.`
        );
        return;
      }
    }

    updateMutation.mutate(overrides, {
      onSuccess: () => {
        toast.success("Cambios guardados");
        setIsDirty(false);
      },
      onError: () => {
        toast.error("Error al guardar los cambios");
      },
    });
  }

  if (variablesMeta.length === 0) {
    return (
      <Card className="border-0 bg-white shadow-[0_12px_32px_rgba(25,28,30,0.06)]">
        <CardContent className="pt-6">
          <p className="text-[#434655]">No se encontraron variables en esta plantilla.</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-2">
      {variablesMeta.map((m) => {
        const row = rows[m.name] ?? initRow(m);
        return (
          <Card
            key={m.name}
            className="border-0 bg-white shadow-[0_2px_8px_rgba(25,28,30,0.04)] hover:shadow-[0_4px_16px_rgba(25,28,30,0.06)] transition-shadow"
          >
            <CardContent className="p-3 space-y-2">
              {/* Header: name + type + help text on a single row when owner */}
              <div className="flex items-center gap-2">
                <span className="font-mono text-sm font-semibold text-[#191c1e] shrink-0 min-w-0 truncate max-w-[180px]">
                  {m.name}
                </span>
                {isOwner ? (
                  <>
                    <Select
                      value={row.type}
                      onValueChange={(v) => setRowType(m.name, v as VariableType)}
                    >
                      <SelectTrigger size="sm" className="w-36 shrink-0">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {(Object.entries(TYPE_LABELS) as [VariableType, string][]).map(
                          ([val, label]) => (
                            <SelectItem key={val} value={val}>
                              {label}
                            </SelectItem>
                          )
                        )}
                      </SelectContent>
                    </Select>
                    <Input
                      value={row.helpText}
                      onChange={(e) => setRowHelpText(m.name, e.target.value)}
                      placeholder="Mensaje de ayuda (ej. formato DD/MM/YYYY)"
                      className="text-sm h-9 flex-1 min-w-0"
                    />
                  </>
                ) : (
                  <>
                    <Badge className="bg-[#e8f0fe] text-[#1a56db] border-0 rounded-full text-xs font-semibold shrink-0">
                      {TYPE_LABELS[m.type ?? "text"]}
                    </Badge>
                    {m.help_text ? (
                      <p className="text-xs text-[#434655] italic flex-1 min-w-0 truncate">
                        {m.help_text}
                      </p>
                    ) : null}
                  </>
                )}
              </div>

              {/* Options (select type only) — full row when present */}
              {isOwner && row.type === "select" && (
                <Textarea
                  value={row.optionsText}
                  onChange={(e) => setRowOptions(m.name, e.target.value)}
                  placeholder="Opciones, una por línea (Bs. / USD / EUR)"
                  className="text-xs min-h-16 resize-none"
                />
              )}
              {!isOwner && m.type === "select" && m.options && m.options.length > 0 && (
                <div className="flex flex-wrap gap-1">
                  {m.options.map((opt) => (
                    <Badge key={opt} variant="outline" className="text-xs rounded-full">
                      {opt}
                    </Badge>
                  ))}
                </div>
              )}

              {/* Contexts collapsible — paragraph contains the variable name highlighted */}
              {m.contexts.length > 0 ? (
                <details className="group">
                  <summary className="cursor-pointer list-none flex items-center gap-1 text-xs text-muted-foreground select-none hover:text-[#004ac6] transition-colors">
                    <span className="group-open:rotate-90 transition-transform inline-block">▶</span>
                    <span>
                      Aparece en {m.contexts.length} párrafo{m.contexts.length !== 1 ? "s" : ""}
                    </span>
                  </summary>
                  <div className="mt-2 space-y-1.5 max-h-48 overflow-y-auto pl-2">
                    {m.contexts.map((ctx, i) => (
                      <blockquote
                        key={i}
                        className="border-l-2 border-[#b4c5ff] pl-3 text-xs text-[#434655] italic leading-relaxed"
                      >
                        <HighlightedContext ctx={ctx} varName={m.name} />
                      </blockquote>
                    ))}
                  </div>
                </details>
              ) : (
                <p className="text-xs text-muted-foreground italic">
                  No aparece en ningún párrafo
                </p>
              )}
            </CardContent>
          </Card>
        );
      })}

      {/* Sticky save/discard bar — owner only */}
      {isOwner && (
        <div className="sticky bottom-0 bg-white/90 backdrop-blur-sm border-t border-border/40 pt-3 pb-1 flex justify-end gap-2">
          <Button
            type="button"
            variant="outline"
            disabled={!isDirty || updateMutation.isPending}
            onClick={handleDiscard}
          >
            Descartar cambios
          </Button>
          <Button
            type="button"
            disabled={!isDirty || updateMutation.isPending}
            onClick={handleSave}
            className="bg-gradient-to-br from-[#004ac6] to-[#2563eb] text-white shadow-[0_2px_8px_rgba(0,74,198,0.3)]"
          >
            {updateMutation.isPending ? "Guardando..." : "Guardar cambios"}
          </Button>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------

interface TemplateDetailProps {
  templateId: string;
}

export default function TemplateDetail({ templateId }: TemplateDetailProps) {
  const { data: template, isLoading } = useTemplate(templateId);
  const deleteTemplate = useDeleteTemplate();
  const uploadNewVersion = useUploadNewVersion();
  const navigate = useNavigate();
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [uploadDialogOpen, setUploadDialogOpen] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const onDrop = useCallback((acceptedFiles: File[]) => {
    if (acceptedFiles.length > 0) {
      setSelectedFile(acceptedFiles[0]);
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        [".docx"],
    },
    maxFiles: 1,
  });

  function handleUploadVersion() {
    if (!selectedFile) return;
    uploadNewVersion.mutate(
      { templateId, file: selectedFile },
      {
        onSuccess: () => {
          toast.success("Nueva versión subida con éxito");
          setUploadDialogOpen(false);
          setSelectedFile(null);
        },
        onError: () => {
          toast.error("Error al subir la nueva versión");
        },
      }
    );
  }

  if (isLoading) return <TemplateDetailSkeleton />;
  if (!template) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-12">
        <p className="text-muted-foreground">Plantilla no encontrada</p>
        <Button variant="outline" onClick={() => navigate({ to: "/templates" })}>
          <ArrowLeft />
          Volver a Plantillas
        </Button>
      </div>
    );
  }

  const currentVersion = template.versions.find(
    (v) => v.version === template.current_version
  );

  function handleDelete() {
    deleteTemplate.mutate(templateId, {
      onSuccess: () => {
        toast.success("Plantilla eliminada con éxito");
        navigate({ to: "/templates" });
      },
      onError: (error: unknown) => {
        const detail =
          error &&
          typeof error === "object" &&
          "response" in error &&
          (error as { response?: { data?: { detail?: string } } }).response
            ?.data?.detail;
        toast.error(
          (detail as string) || "Error al eliminar la plantilla"
        );
      },
    });
    setDeleteDialogOpen(false);
  }

  const accessBadgeLabel =
    template.access_type === "shared" ? "Compartido contigo" : null;

  const isOwnerOrAdmin =
    template.is_owner || template.access_type === "admin";

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start gap-4">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => navigate({ to: "/templates" })}
        >
          <ArrowLeft />
        </Button>
        <div className="flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-2xl font-bold">{template.name}</h1>
            {accessBadgeLabel && (
              <Badge className="bg-[#e8f0fe] text-[#1a56db] border-0 rounded-full text-xs font-semibold">
                {accessBadgeLabel}
              </Badge>
            )}
          </div>
          {template.description && (
            <p className="mt-1 text-muted-foreground">{template.description}</p>
          )}
        </div>
      </div>

      {/* Action Bar */}
      <div className="flex flex-wrap gap-2">
        {currentVersion && (
          <>
            <Button
              className="bg-gradient-to-br from-[#004ac6] to-[#2563eb] text-white shadow-[0_4px_12px_rgba(0,74,198,0.3)] hover:shadow-[0_6px_20px_rgba(0,74,198,0.4)] transition-all"
              onClick={() =>
                navigate({
                  to: "/documents/generate/$versionId",
                  params: { versionId: currentVersion.id },
                  search: { templateId },
                })
              }
            >
              <FileText />
              Generar Documento
            </Button>
            <Button
              variant="outline"
              className="border-[rgba(195,198,215,0.3)] hover:bg-[#dbe1ff]/50 hover:text-[#004ac6] transition-all"
              onClick={() =>
                navigate({
                  to: "/documents/bulk/$versionId",
                  params: { versionId: currentVersion.id },
                  search: { templateId },
                })
              }
            >
              <Files />
              Generación Masiva
            </Button>
          </>
        )}

        {template.is_owner && (
          <ShareTemplateDialog
            templateId={templateId}
            templateName={template.name}
          />
        )}

        {template.is_owner && (
          <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
            <DialogTrigger
              render={
                <Button variant="destructive">
                  <Trash2 />
                  Eliminar Plantilla
                </Button>
              }
            />
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Eliminar Plantilla</DialogTitle>
                <DialogDescription>
                  ¿Está seguro de que desea eliminar "{template.name}"? Esta acción
                  no se puede deshacer. Todas las versiones serán eliminadas permanentemente.
                </DialogDescription>
              </DialogHeader>
              <DialogFooter>
                <Button
                  variant="outline"
                  onClick={() => setDeleteDialogOpen(false)}
                >
                  Cancelar
                </Button>
                <Button
                  variant="destructive"
                  onClick={handleDelete}
                  disabled={deleteTemplate.isPending}
                >
                  {deleteTemplate.isPending ? "Eliminando..." : "Eliminar"}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        )}
      </div>

      {/* Tabs */}
      <Tabs defaultValue="info">
        <TabsList>
          <TabsTrigger value="info">
            <Info className="size-3.5" />
            Información
          </TabsTrigger>
          <TabsTrigger value="variables">
            <Variable className="size-3.5" />
            Variables
          </TabsTrigger>
          <TabsTrigger value="versions">
            <Clock className="size-3.5" />
            Versiones
          </TabsTrigger>
          {isOwnerOrAdmin && (
            <TabsTrigger value="shares">
              <Share2 className="size-3.5" />
              Compartido con
            </TabsTrigger>
          )}
          <TabsTrigger value="documents">
            <Files className="size-3.5" />
            Documentos
          </TabsTrigger>
        </TabsList>

        {/* Info Tab */}
        <TabsContent value="info">
          <Card className="border-0 bg-white shadow-[0_12px_32px_rgba(25,28,30,0.06)]">
            <CardHeader>
              <CardTitle>Información de la Plantilla</CardTitle>
            </CardHeader>
            <CardContent>
              <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-3">
                <dt className="text-[#434655]">Versión Actual</dt>
                <dd className="font-medium">v{template.current_version}</dd>

                <dt className="text-[#434655]">Creado</dt>
                <dd>{formatDate(template.created_at)}</dd>

                <dt className="text-[#434655]">Actualizado</dt>
                <dd>{formatDate(template.updated_at)}</dd>

                {currentVersion && (
                  <>
                    <dt className="text-[#434655]">Tamaño del Archivo</dt>
                    <dd>{formatFileSize(currentVersion.file_size)}</dd>
                  </>
                )}

                <dt className="text-[#434655]">Total de Versiones</dt>
                <dd>{template.versions.length}</dd>
              </dl>
              {template.shared_by_email && (
                <p className="mt-4 text-sm text-muted-foreground">
                  <span className="font-medium">Compartido por:</span>{" "}
                  {template.shared_by_email}
                </p>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Variables Tab */}
        <TabsContent value="variables">
          {currentVersion ? (
            <VariablesTab
              templateId={templateId}
              versionId={currentVersion.id}
              variablesMeta={currentVersion.variables_meta}
              isOwner={template.is_owner}
            />
          ) : (
            <Card className="border-0 bg-white shadow-[0_12px_32px_rgba(25,28,30,0.06)]">
              <CardContent className="pt-6">
                <p className="text-[#434655]">No se encontraron variables en esta plantilla.</p>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Versions Tab */}
        <TabsContent value="versions">
          <div className="space-y-3">
            {template.is_owner && (
              <Dialog
                open={uploadDialogOpen}
                onOpenChange={setUploadDialogOpen}
              >
                <DialogTrigger
                  render={
                    <Button className="bg-gradient-to-br from-[#004ac6] to-[#2563eb] text-white shadow-[0_4px_12px_rgba(0,74,198,0.3)] hover:shadow-[0_6px_20px_rgba(0,74,198,0.4)] transition-all">
                      <Upload className="size-4" />
                      Subir Nueva Versión
                    </Button>
                  }
                />
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>Subir Nueva Versión</DialogTitle>
                    <DialogDescription>
                      Suba un nuevo archivo .docx para crear la versión v
                      {template.current_version + 1} de "{template.name}".
                    </DialogDescription>
                  </DialogHeader>
                  <div
                    {...getRootProps()}
                    className={`flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed p-10 transition-all ${
                      isDragActive
                        ? "border-[#004ac6] bg-[#dbe1ff]/30"
                        : "border-[rgba(195,198,215,0.4)] hover:border-[#2563eb]/50 hover:bg-[#f7f9fb]"
                    }`}
                  >
                    <input {...getInputProps()} />
                    <Upload className="mb-2 size-8 text-[#434655]" />
                    {selectedFile ? (
                      <p className="text-sm font-medium">{selectedFile.name}</p>
                    ) : isDragActive ? (
                      <p className="text-sm text-muted-foreground">
                        Suelte el archivo aquí...
                      </p>
                    ) : (
                      <p className="text-sm text-muted-foreground">
                        Arrastre y suelte un archivo .docx, o haga clic para seleccionar
                      </p>
                    )}
                  </div>
                  <DialogFooter>
                    <Button
                      variant="outline"
                      onClick={() => {
                        setUploadDialogOpen(false);
                        setSelectedFile(null);
                      }}
                    >
                      Cancelar
                    </Button>
                    <Button
                      onClick={handleUploadVersion}
                      disabled={!selectedFile || uploadNewVersion.isPending}
                    >
                      {uploadNewVersion.isPending
                        ? "Subiendo..."
                        : "Subir Versión"}
                    </Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
            )}

            {template.versions
              .sort((a, b) => b.version - a.version)
              .map((version) => (
                <Card key={version.id} size="sm" className="border-0 bg-white shadow-[0_4px_16px_rgba(25,28,30,0.04)] hover:shadow-[0_8px_24px_rgba(25,28,30,0.08)] transition-shadow">
                  <CardContent>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <Badge
                          className={
                            version.version === template.current_version
                              ? "bg-gradient-to-br from-[#004ac6] to-[#2563eb] text-white border-0 rounded-full"
                              : "border-[#2563eb]/30 text-[#004ac6] bg-transparent rounded-full"
                          }
                          variant={
                            version.version === template.current_version
                              ? "default"
                              : "outline"
                          }
                        >
                          v{version.version}
                        </Badge>
                        <span className="text-[#434655]">
                          {version.variables.length} variable
                          {version.variables.length !== 1 ? "s" : ""}
                        </span>
                        <span className="text-[#434655]">
                          {formatFileSize(version.file_size)}
                        </span>
                      </div>
                      <span className="text-sm text-[#434655]">
                        {formatDate(version.created_at)}
                      </span>
                    </div>
                  </CardContent>
                </Card>
              ))}
          </div>
        </TabsContent>

        {/* Shares Tab — visible to owner and admin only */}
        {isOwnerOrAdmin && (
          <TabsContent value="shares">
            <SharesTab templateId={templateId} templateName={template.name} />
          </TabsContent>
        )}

        {/* Documents Tab */}
        <TabsContent value="documents">
          <DocumentsTab templateId={templateId} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
