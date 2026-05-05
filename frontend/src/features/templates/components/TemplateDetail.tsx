import { Fragment, useCallback, useMemo, useState } from "react";
import { Link, useNavigate } from "@tanstack/react-router";
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
  Sparkles,
  FileSpreadsheet,
  CircleAlert,
  BookOpen,
} from "lucide-react";

import {
  useTemplate,
  useDeleteTemplate,
  useUploadNewVersion,
  useTemplateShares,
} from "@/features/templates/api";
import { useDocuments } from "@/features/documents/api/queries";
import type { VariableMeta, VariableType } from "@/features/templates/api/queries";
import {
  useUpdateVariableTypes,
  type VariableTypeOverrideInput,
} from "@/features/templates/api/mutations";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
import { Label } from "@/components/ui/label";
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
 * Renders a paragraph and highlights every `{{ var }}` placeholder inside it.
 * The placeholder matching `active` gets the amber chip; other placeholders in
 * the same paragraph render as muted grey chips so the user can see the active
 * variable in context without losing track of the others.
 */
function ParagraphPreview({ text, active }: { text: string; active: string }) {
  const parts = text.split(/(\{\{\s*[a-zA-Z_][a-zA-Z0-9_]*\s*\}\})/g);
  return (
    <p className="m-0 text-[13px] leading-[1.65] text-[var(--fg-1)]">
      {parts.map((part, i) => {
        const m = part.match(/\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}/);
        if (!m) return <Fragment key={i}>{part}</Fragment>;
        const varName = m[1];
        const isActive = varName === active;
        return (
          <span
            key={i}
            className={`var-chip ${isActive ? "var-chip-active" : "var-chip-muted"}`}
            title={isActive ? `Variable seleccionada: ${varName}` : `Otra variable: ${varName}`}
          >
            {`{{ ${varName} }}`}
          </span>
        );
      })}
    </p>
  );
}

function VariablesTab({ templateId, versionId, variablesMeta, isOwner }: VariablesTabProps) {
  const [rows, setRows] = useState<Record<string, VariableRowState>>(() =>
    Object.fromEntries(variablesMeta.map((m) => [m.name, initRow(m)]))
  );
  const [isDirty, setIsDirty] = useState(false);
  const [query, setQuery] = useState("");
  const [selectedName, setSelectedName] = useState<string>(
    () => variablesMeta[0]?.name ?? ""
  );

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

  const filtered = useMemo(
    () =>
      variablesMeta.filter((m) =>
        m.name.toLowerCase().includes(query.toLowerCase())
      ),
    [variablesMeta, query]
  );

  const activeMeta =
    variablesMeta.find((m) => m.name === selectedName) ?? variablesMeta[0];
  const activeRow = activeMeta
    ? rows[activeMeta.name] ?? initRow(activeMeta)
    : null;

  if (variablesMeta.length === 0) {
    return (
      <Card className="border-0 bg-white shadow-[var(--shadow-md)]">
        <CardContent className="pt-6">
          <p className="text-[var(--fg-2)]">
            No se encontraron variables en esta plantilla.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div>
      <div className="grid gap-4 lg:grid-cols-[280px_1fr]">
        {/* Left rail — variable list */}
        <div className="flex max-h-[calc(100vh-280px)] flex-col overflow-hidden rounded-xl bg-white shadow-[var(--shadow-sm)] ring-1 ring-[rgba(195,198,215,0.30)]">
          <div className="border-b border-[rgba(195,198,215,0.20)] px-4 py-3">
            <div className="mb-2 text-[13px] font-semibold text-[var(--fg-1)]">
              Variables detectadas
            </div>
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Buscar variable…"
              className="h-9 text-sm"
            />
            <div className="mt-2 text-[11px] text-[var(--fg-3)]">
              {variablesMeta.length} marcadores · click para ver párrafos
            </div>
          </div>
          <div className="flex-1 overflow-y-auto">
            {filtered.length === 0 ? (
              <div className="px-4 py-6 text-center text-[12.5px] text-[var(--fg-3)]">
                Sin resultados
              </div>
            ) : (
              filtered.map((m) => {
                const row = rows[m.name] ?? initRow(m);
                const isSelected = m.name === activeMeta?.name;
                return (
                  <button
                    type="button"
                    key={m.name}
                    onClick={() => setSelectedName(m.name)}
                    className={`flex w-full items-center gap-2 border-b border-[rgba(195,198,215,0.15)] px-4 py-2.5 text-left transition-colors last:border-b-0 ${
                      isSelected
                        ? "bg-[var(--bg-accent)]"
                        : "hover:bg-[var(--bg-page)]"
                    }`}
                  >
                    <span
                      className={`min-w-0 flex-1 truncate font-mono text-[12.5px] ${
                        isSelected
                          ? "font-semibold text-[var(--primary)]"
                          : "text-[var(--fg-1)]"
                      }`}
                    >
                      {m.name}
                    </span>
                    <Badge
                      variant="outline"
                      className="rounded-full border-[rgba(195,198,215,0.40)] px-1.5 text-[10px] text-[var(--fg-3)]"
                    >
                      {m.contexts.length}×
                    </Badge>
                    <Badge
                      className={`rounded-full border-0 px-1.5 text-[10px] font-semibold ${
                        isSelected
                          ? "bg-white text-[var(--primary)]"
                          : "bg-[var(--bg-muted)] text-[var(--fg-3)]"
                      }`}
                    >
                      {TYPE_LABELS[row.type]}
                    </Badge>
                  </button>
                );
              })
            )}
          </div>
        </div>

        {/* Right pane — variable detail */}
        {activeMeta && activeRow && (
          <div className="flex min-w-0 flex-col gap-4">
            {/* Editor card */}
            <div className="rounded-xl bg-white p-5 shadow-[var(--shadow-sm)] ring-1 ring-[rgba(195,198,215,0.30)]">
              <div className="mb-4 flex flex-wrap items-center gap-2">
                <span className="font-mono text-[15px] font-semibold text-[var(--primary)]">
                  {`{{ ${activeMeta.name} }}`}
                </span>
                <Badge className="rounded-full border-0 bg-[var(--bg-accent)] font-semibold text-[var(--primary)] hover:bg-[var(--bg-accent)]">
                  {TYPE_LABELS[activeRow.type]}
                </Badge>
                <Badge
                  variant="outline"
                  className="rounded-full border-[rgba(195,198,215,0.40)] text-[var(--fg-3)]"
                >
                  {activeMeta.contexts.length} aparición
                  {activeMeta.contexts.length === 1 ? "" : "es"}
                </Badge>
              </div>

              {isOwner ? (
                <>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <div className="grid gap-1.5">
                      <Label className="text-[12.5px] font-medium text-[var(--fg-2)]">
                        Tipo de dato
                      </Label>
                      <Select
                        value={activeRow.type}
                        onValueChange={(v) =>
                          setRowType(activeMeta.name, v as VariableType)
                        }
                      >
                        <SelectTrigger>
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
                    </div>
                    <div className="grid gap-1.5">
                      <Label className="text-[12.5px] font-medium text-[var(--fg-2)]">
                        Mensaje de ayuda
                      </Label>
                      <Input
                        value={activeRow.helpText}
                        onChange={(e) =>
                          setRowHelpText(activeMeta.name, e.target.value)
                        }
                        placeholder="ej. formato DD/MM/YYYY"
                      />
                    </div>
                  </div>
                  {activeRow.type === "select" && (
                    <div className="mt-3 grid gap-1.5">
                      <Label className="text-[12.5px] font-medium text-[var(--fg-2)]">
                        Opciones (una por línea)
                      </Label>
                      <Textarea
                        value={activeRow.optionsText}
                        onChange={(e) =>
                          setRowOptions(activeMeta.name, e.target.value)
                        }
                        placeholder="Bs.&#10;USD&#10;EUR"
                        className="min-h-20 resize-none text-sm"
                      />
                    </div>
                  )}
                </>
              ) : (
                <div className="space-y-2">
                  {activeMeta.help_text && (
                    <p className="m-0 text-[13px] italic text-[var(--fg-2)]">
                      {activeMeta.help_text}
                    </p>
                  )}
                  {activeMeta.type === "select" &&
                    activeMeta.options &&
                    activeMeta.options.length > 0 && (
                      <div className="flex flex-wrap gap-1">
                        {activeMeta.options.map((opt) => (
                          <Badge
                            key={opt}
                            variant="outline"
                            className="rounded-full text-xs"
                          >
                            {opt}
                          </Badge>
                        ))}
                      </div>
                    )}
                </div>
              )}
            </div>

            {/* Contexts card */}
            <div className="overflow-hidden rounded-xl bg-white shadow-[var(--shadow-sm)] ring-1 ring-[rgba(195,198,215,0.30)]">
              <div className="border-b border-[rgba(195,198,215,0.20)] px-5 py-3">
                <div className="text-[13px] font-semibold text-[var(--fg-1)]">
                  Aparece en {activeMeta.contexts.length} párrafo
                  {activeMeta.contexts.length === 1 ? "" : "s"}
                </div>
                <div className="mt-1.5 flex flex-wrap items-center gap-3 text-[11px] text-[var(--fg-3)]">
                  <span className="inline-flex items-center gap-1.5">
                    <span className="inline-block size-2.5 rounded bg-gradient-to-br from-[#fef3c7] to-[#fde68a] ring-1 ring-[#f59e0b]" />
                    seleccionada
                  </span>
                  <span className="inline-flex items-center gap-1.5">
                    <span className="inline-block size-2.5 rounded bg-[var(--bg-muted)] ring-1 ring-[rgba(195,198,215,0.40)]" />
                    otras variables del párrafo
                  </span>
                </div>
              </div>
              {activeMeta.contexts.length === 0 ? (
                <div className="px-5 py-8 text-center text-[12.5px] text-[var(--fg-3)]">
                  No hay vista previa de párrafos para esta variable.
                </div>
              ) : (
                <div className="flex flex-col">
                  {activeMeta.contexts.map((ctx, i) => (
                    <div
                      key={i}
                      className="flex gap-3 border-t border-[rgba(195,198,215,0.15)] px-5 py-3 first:border-t-0"
                    >
                      <div className="flex min-w-[60px] shrink-0 flex-col text-[11px] text-[var(--fg-3)]">
                        <span className="font-mono">¶ {i + 1}</span>
                      </div>
                      <div className="min-w-0 flex-1">
                        <ParagraphPreview text={ctx} active={activeMeta.name} />
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Sticky save/discard bar — owner only */}
      {isOwner && (
        <div className="sticky bottom-0 mt-4 flex justify-end gap-2 border-t border-[rgba(195,198,215,0.20)] bg-white/90 pt-3 pb-1 backdrop-blur-sm">
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
            className="bg-gradient-to-br from-[#004ac6] to-[#2563eb] font-semibold text-white shadow-[var(--shadow-brand-sm)] hover:shadow-[var(--shadow-brand-md)]"
          >
            {updateMutation.isPending ? "Guardando…" : "Guardar cambios"}
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
  const { data: documentsData } = useDocuments({ template_id: templateId, page: 1, size: 1 });
  const { data: shares } = useTemplateShares(templateId);
  const deleteTemplate = useDeleteTemplate();
  const uploadNewVersion = useUploadNewVersion();
  const navigate = useNavigate();
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState("");
  const [shareDialogOpen, setShareDialogOpen] = useState(false);
  const [uploadDialogOpen, setUploadDialogOpen] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  type DetailTab = "info" | "variables" | "versions" | "shares" | "documents";
  const [activeTab, setActiveTab] = useState<DetailTab>("info");

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

  const isOwnerOrAdmin =
    template.is_owner || template.access_type === "admin";

  return (
    <div className="space-y-5">
      {/* Back link */}
      <Link
        to="/templates"
        className="-ml-1 inline-flex items-center gap-1 text-[12.5px] font-medium text-[var(--fg-3)] transition-colors hover:text-[var(--primary)]"
      >
        <ArrowLeft className="size-3.5" />
        Volver a Plantillas
      </Link>

      {/* Header */}
      <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
        <div className="flex items-start gap-3.5">
          <span className="inline-flex size-12 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-[#dbe1ff] to-[#b4c5ff] text-[var(--primary)]">
            <FileText className="size-5" />
          </span>
          <div className="min-w-0">
            <div className="mb-1.5 flex flex-wrap items-center gap-1.5">
              <Badge variant="outline" className="rounded-full border-[rgba(37,99,235,0.30)] text-[var(--primary)]">
                v{template.current_version}
              </Badge>
              {template.access_type === "shared" && (
                <Badge className="rounded-full border-0 bg-[var(--bg-accent)] text-[var(--primary)] hover:bg-[var(--bg-accent)]">
                  Compartida
                </Badge>
              )}
            </div>
            <h1 className="m-0 max-w-[680px] text-[22px] font-bold tracking-tight text-[var(--fg-1)]">
              {template.name}
            </h1>
            {template.description && (
              <p className="mt-1.5 text-[13px] text-[var(--fg-3)]">{template.description}</p>
            )}
            {template.shared_by_email && (
              <p className="mt-1.5 text-xs text-[var(--fg-3)]">
                Compartida por <span className="font-mono text-[var(--primary)]">{template.shared_by_email}</span>
              </p>
            )}
          </div>
        </div>

        {/* Action row */}
        <div className="flex flex-wrap items-center gap-1.5">
          {currentVersion && (
            <>
              <Button
                size="sm"
                onClick={() =>
                  navigate({
                    to: "/documents/generate/$versionId",
                    params: { versionId: currentVersion.id },
                    search: { templateId },
                  })
                }
                className="bg-gradient-to-br from-[#004ac6] to-[#2563eb] font-semibold text-white shadow-[var(--shadow-brand-sm)] hover:shadow-[var(--shadow-brand-md)]"
              >
                <Sparkles className="size-3.5" />
                Generar Documento
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() =>
                  navigate({
                    to: "/documents/bulk/$versionId",
                    params: { versionId: currentVersion.id },
                    search: { templateId },
                  })
                }
              >
                <FileSpreadsheet className="size-3.5" />
                Generación Masiva
              </Button>
            </>
          )}
          {template.is_owner && (
            <Button variant="outline" size="sm" onClick={() => setShareDialogOpen(true)}>
              <Share2 className="size-3.5" />
              Compartir
            </Button>
          )}
          {template.is_owner && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setDeleteConfirm("");
                setDeleteDialogOpen(true);
              }}
              className="border-[rgba(186,26,26,0.25)] text-[var(--destructive)] hover:bg-[#ffdad6]/50 hover:text-[var(--destructive)]"
            >
              <Trash2 className="size-3.5" />
              Eliminar
            </Button>
          )}
        </div>
      </div>

      {/* Sidebar layout */}
      <div className="grid gap-6 lg:grid-cols-[220px_1fr]">
        <aside className="self-start lg:sticky lg:top-20">
          <nav className="flex flex-col gap-0.5">
            <SidebarItem
              icon={<Info className="size-4" />}
              active={activeTab === "info"}
              onClick={() => setActiveTab("info")}
            >
              Información
            </SidebarItem>
            <SidebarItem
              icon={<Variable className="size-4" />}
              active={activeTab === "variables"}
              onClick={() => setActiveTab("variables")}
              count={currentVersion?.variables.length}
            >
              Variables
            </SidebarItem>
            <SidebarItem
              icon={<Clock className="size-4" />}
              active={activeTab === "versions"}
              onClick={() => setActiveTab("versions")}
              count={template.versions.length}
            >
              Versiones
            </SidebarItem>
            {isOwnerOrAdmin && (
              <SidebarItem
                icon={<Share2 className="size-4" />}
                active={activeTab === "shares"}
                onClick={() => setActiveTab("shares")}
              >
                Compartido
              </SidebarItem>
            )}
            <SidebarItem
              icon={<Files className="size-4" />}
              active={activeTab === "documents"}
              onClick={() => setActiveTab("documents")}
            >
              Documentos
            </SidebarItem>
          </nav>
        </aside>

        <div className="min-w-0">
          {activeTab === "info" && (
            <div className="grid gap-4 lg:grid-cols-[1.6fr_1fr]">
              <Card className="border-0 bg-white shadow-[var(--shadow-md)]">
                <CardHeader className="border-b border-[rgba(195,198,215,0.20)]">
                  <CardTitle>Información de la plantilla</CardTitle>
                </CardHeader>
                <CardContent className="p-0">
                  {[
                    ["Versión actual", `v${template.current_version}`],
                    ["Creado", formatDate(template.created_at)],
                    ["Actualizado", formatDate(template.updated_at)],
                    ...(currentVersion
                      ? [["Tamaño del archivo", formatFileSize(currentVersion.file_size)]]
                      : []),
                    ["Total de versiones", String(template.versions.length)],
                    ["Variables detectadas", `${currentVersion?.variables.length ?? 0} marcadores`],
                    ...(template.shared_by_email
                      ? [["Compartida por", template.shared_by_email]]
                      : []),
                  ].map(([k, v], i) => (
                    <div
                      key={k}
                      className={`flex items-center px-5 py-2.5 text-[13.5px] ${
                        i ? "border-t border-[rgba(195,198,215,0.15)]" : ""
                      }`}
                    >
                      <div className="w-[180px] shrink-0 text-[12.5px] text-[var(--fg-3)]">{k}</div>
                      <div className="font-medium text-[var(--fg-1)]">{v}</div>
                    </div>
                  ))}
                </CardContent>
              </Card>

              <div className="flex flex-col gap-4">
                <Card className="border-0 bg-white shadow-[var(--shadow-md)]">
                  <CardHeader>
                    <CardTitle className="text-base">Resumen de uso</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-2 gap-2.5">
                      <UsageStat value={documentsData?.total ?? 0} label="documentos generados" />
                      {isOwnerOrAdmin && (
                        <UsageStat value={shares?.length ?? 0} label="usuarios con acceso" />
                      )}
                      <UsageStat value={template.versions.length} label="versiones publicadas" />
                      <UsageStat
                        value={currentVersion?.variables.length ?? 0}
                        label="variables detectadas"
                      />
                    </div>
                  </CardContent>
                </Card>

                <div className="flex items-start gap-2.5 rounded-[10px] bg-[var(--bg-accent)] px-3.5 py-3 text-[13px] leading-[1.45] text-[var(--primary)]">
                  <BookOpen className="mt-px size-4 shrink-0" />
                  <div className="flex-1">
                    ¿Dudas con marcadores{" "}
                    <span className="font-mono">{"{{ var }}"}</span>? Usá el botón{" "}
                    <strong className="font-semibold">Guía de Plantillas</strong> arriba para ver la documentación completa.
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeTab === "variables" && (
            currentVersion ? (
              <VariablesTab
                templateId={templateId}
                versionId={currentVersion.id}
                variablesMeta={currentVersion.variables_meta}
                isOwner={template.is_owner}
              />
            ) : (
              <Card className="border-0 bg-white shadow-[var(--shadow-md)]">
                <CardContent className="pt-6">
                  <p className="text-[var(--fg-2)]">No se encontraron variables en esta plantilla.</p>
                </CardContent>
              </Card>
            )
          )}

          {activeTab === "versions" && (
            <div className="space-y-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h3 className="m-0 text-lg font-bold tracking-tight text-[var(--fg-1)]">
                    Historial de versiones
                  </h3>
                  <p className="mt-1 text-[12.5px] text-[var(--fg-3)]">
                    Cada versión preserva las variables y el archivo original.
                  </p>
                </div>
                {template.is_owner && (
                  <Dialog open={uploadDialogOpen} onOpenChange={setUploadDialogOpen}>
                    <DialogTrigger
                      render={
                        <Button
                          size="sm"
                          className="bg-gradient-to-br from-[#004ac6] to-[#2563eb] font-semibold text-white shadow-[var(--shadow-brand-sm)] hover:shadow-[var(--shadow-brand-md)]"
                        />
                      }
                    >
                      <Upload className="size-3.5" />
                      Subir Nueva Versión
                    </DialogTrigger>
                    <DialogContent>
                      <DialogHeader>
                        <DialogTitle>Subir nueva versión</DialogTitle>
                        <DialogDescription>
                          Suba un nuevo archivo .docx para crear la versión v
                          {template.current_version + 1} de "{template.name}".
                        </DialogDescription>
                      </DialogHeader>
                      <div
                        {...getRootProps()}
                        className={`flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed p-10 text-center transition-all ${
                          isDragActive
                            ? "border-[var(--primary)] bg-[var(--bg-accent)]/50"
                            : "border-[rgba(195,198,215,0.45)] hover:border-[var(--ring)]/40 hover:bg-[var(--bg-page)]"
                        }`}
                      >
                        <input {...getInputProps()} />
                        <Upload
                          className={`size-8 ${isDragActive ? "text-[var(--primary)]" : "text-[var(--fg-3)]"}`}
                        />
                        {selectedFile ? (
                          <p className="text-sm font-semibold text-[var(--fg-1)]">
                            {selectedFile.name}
                          </p>
                        ) : isDragActive ? (
                          <p className="text-sm font-semibold text-[var(--fg-1)]">
                            Suelte aquí
                          </p>
                        ) : (
                          <>
                            <p className="text-sm font-semibold text-[var(--fg-1)]">
                              Arrastre y suelte un archivo .docx
                            </p>
                            <p className="text-xs text-[var(--fg-3)]">
                              o haga clic para seleccionar · máx. 10 MB
                            </p>
                          </>
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
                          className="bg-gradient-to-br from-[#004ac6] to-[#2563eb] font-semibold text-white shadow-[var(--shadow-brand-sm)] hover:shadow-[var(--shadow-brand-md)]"
                        >
                          {uploadNewVersion.isPending ? "Subiendo…" : "Subir Versión"}
                        </Button>
                      </DialogFooter>
                    </DialogContent>
                  </Dialog>
                )}
              </div>

              <div className="flex flex-col gap-2.5">
                {template.versions
                  .sort((a, b) => b.version - a.version)
                  .map((version) => {
                    const isCurrent = version.version === template.current_version;
                    return (
                      <div
                        key={version.id}
                        className="flex items-center gap-3.5 rounded-xl bg-white p-4 shadow-[var(--shadow-sm)] ring-1 ring-[rgba(195,198,215,0.30)] transition-shadow hover:shadow-[var(--shadow-md)]"
                      >
                        <span
                          className={`inline-flex size-10 shrink-0 items-center justify-center rounded-[10px] text-[13px] font-bold tracking-tight ${
                            isCurrent
                              ? "bg-gradient-to-br from-[#004ac6] to-[#2563eb] text-white shadow-[var(--shadow-brand-sm)]"
                              : "bg-[var(--bg-muted)] text-[var(--fg-3)]"
                          }`}
                        >
                          v{version.version}
                        </span>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-semibold text-[var(--fg-1)]">
                              Versión {version.version}
                            </span>
                            {isCurrent && (
                              <Badge className="rounded-full border-0 bg-[#d1fae5] text-[#065f46] hover:bg-[#d1fae5]">
                                Actual
                              </Badge>
                            )}
                          </div>
                          <div className="mt-0.5 text-[12px] text-[var(--fg-3)]">
                            {version.variables.length} variable
                            {version.variables.length !== 1 ? "s" : ""} ·{" "}
                            {formatFileSize(version.file_size)} · {formatDate(version.created_at)}
                          </div>
                        </div>
                      </div>
                    );
                  })}
              </div>
            </div>
          )}

          {activeTab === "shares" && isOwnerOrAdmin && (
            <SharesTab templateId={templateId} templateName={template.name} />
          )}

          {activeTab === "documents" && <DocumentsTab templateId={templateId} />}
        </div>
      </div>

      {/* Share dialog (controlled from action row) */}
      {template.is_owner && (
        <ShareTemplateDialog
          templateId={templateId}
          templateName={template.name}
          open={shareDialogOpen}
          onOpenChange={setShareDialogOpen}
        />
      )}

      {/* Delete dialog with confirm-by-typing */}
      {template.is_owner && (
        <Dialog
          open={deleteDialogOpen}
          onOpenChange={(o) => {
            setDeleteDialogOpen(o);
            if (!o) setDeleteConfirm("");
          }}
        >
          <DialogContent className="sm:max-w-md">
            <DialogHeader>
              <DialogTitle>Eliminar plantilla</DialogTitle>
            </DialogHeader>
            <div className="flex items-start gap-2.5 rounded-[10px] bg-[#ffdad6] px-3.5 py-3 text-[13px] leading-[1.45] text-[#93000a]">
              <CircleAlert className="mt-px size-4 shrink-0 text-[var(--destructive)]" />
              <div className="flex-1">
                <strong className="font-semibold">Esta acción no se puede deshacer.</strong>{" "}
                Se eliminarán todas las versiones, configuraciones de variables y el historial asociado.
              </div>
            </div>
            <p className="text-[13.5px] leading-[1.55] text-[var(--fg-2)]">
              ¿Está seguro de eliminar la plantilla{" "}
              <strong className="text-[var(--fg-1)]">"{template.name}"</strong>?
            </p>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="delete-confirm" className="text-[12.5px] font-medium text-[var(--fg-2)]">
                Para confirmar, escriba{" "}
                <span className="font-mono text-[var(--destructive)]">ELIMINAR</span>
              </Label>
              <Input
                id="delete-confirm"
                value={deleteConfirm}
                onChange={(e) => setDeleteConfirm(e.target.value)}
                placeholder="ELIMINAR"
                autoFocus
              />
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setDeleteDialogOpen(false)}>
                Cancelar
              </Button>
              <Button
                onClick={handleDelete}
                disabled={deleteConfirm !== "ELIMINAR" || deleteTemplate.isPending}
                className="bg-[var(--destructive)] font-semibold text-white hover:bg-[#93000a]"
              >
                <Trash2 className="size-3.5" />
                {deleteTemplate.isPending ? "Eliminando…" : "Eliminar permanentemente"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
}

function UsageStat({ value, label }: { value: number; label: string }) {
  return (
    <div className="rounded-[10px] bg-[var(--bg-page)] px-3 py-3 ring-1 ring-[rgba(195,198,215,0.30)]">
      <div className="text-2xl font-bold tracking-tight text-[var(--fg-1)]">{value}</div>
      <div className="text-[11.5px] text-[var(--fg-3)]">{label}</div>
    </div>
  );
}

function SidebarItem({
  icon,
  active,
  count,
  onClick,
  children,
}: {
  icon: React.ReactNode;
  active: boolean;
  count?: number;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex items-center gap-2 rounded-lg px-3 py-2 text-left text-sm transition-colors ${
        active
          ? "bg-[var(--bg-accent)] font-semibold text-[var(--primary)]"
          : "text-[var(--fg-2)] hover:bg-[var(--bg-muted)]"
      }`}
    >
      {icon}
      <span className="flex-1">{children}</span>
      {count != null && (
        <span
          className={`inline-flex h-[18px] items-center justify-center rounded-full px-1.5 text-[10.5px] font-semibold ${
            active
              ? "bg-white text-[var(--primary)]"
              : "bg-[var(--bg-muted)] text-[var(--fg-3)]"
          }`}
        >
          {count}
        </span>
      )}
    </button>
  );
}
