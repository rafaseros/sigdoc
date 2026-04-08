import { useState, useCallback, Fragment } from "react";
import { useDropzone } from "react-dropzone";
import { toast } from "sonner";
import {
  UploadIcon,
  FileIcon,
  XIcon,
  LoaderCircleIcon,
  CircleCheckIcon,
  CircleAlertIcon,
  WrenchIcon,
  ChevronRightIcon,
} from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import {
  useUploadTemplate,
  useValidateTemplate,
  useAutoFixTemplate,
  type ValidationResult,
  type ValidationError,
  type VariableSummary,
} from "../api";

type Step = "select" | "validating" | "valid" | "errors";

export function UploadTemplateDialog() {
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState<Step>("select");
  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [validation, setValidation] = useState<ValidationResult | null>(null);

  const validateMutation = useValidateTemplate();
  const autoFixMutation = useAutoFixTemplate();
  const uploadMutation = useUploadTemplate();

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    if (acceptedFiles.length === 0) return;

    const selected = acceptedFiles[0];
    setFile(selected);
    setName(selected.name.replace(/\.docx$/, ""));
    setStep("validating");

    try {
      const result = await validateMutation.mutateAsync(selected);
      setValidation(result);
      setStep(result.valid ? "valid" : "errors");
    } catch {
      toast.error("Error al validar la plantilla");
      setStep("select");
    }
  }, [validateMutation]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        [".docx"],
    },
    maxFiles: 1,
    disabled: step === "validating",
  });

  function handleReset() {
    setFile(null);
    setName("");
    setDescription("");
    setValidation(null);
    setStep("select");
  }

  async function handleAutoFix() {
    if (!file) return;
    try {
      await autoFixMutation.mutateAsync(file);
      toast.success(
        "Archivo corregido descargado. Suba el archivo corregido para continuar."
      );
      setFile(null);
      setValidation(null);
      setStep("select");
    } catch {
      toast.error("Error al auto-corregir la plantilla");
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();

    if (!file || !name.trim()) return;

    try {
      await uploadMutation.mutateAsync({
        file,
        name: name.trim(),
        description: description.trim() || undefined,
      });
      toast.success("Plantilla subida con éxito");
      handleReset();
      setOpen(false);
    } catch (error: unknown) {
      const message =
        error instanceof Error ? error.message : "Error al subir la plantilla";
      toast.error(message);
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(isOpen) => {
        setOpen(isOpen);
        if (!isOpen) handleReset();
      }}
    >
      <DialogTrigger render={<Button />}>
        <UploadIcon className="size-4 mr-2" />
        Subir Plantilla
      </DialogTrigger>
      <DialogContent className="sm:max-w-3xl max-h-[85vh] overflow-y-auto bg-white/80 backdrop-blur-xl border-0 shadow-[0_12px_32px_rgba(25,28,30,0.1)]">
        <DialogHeader>
          <DialogTitle>Subir Plantilla</DialogTitle>
          <DialogDescription>
            Suba una plantilla .docx con marcadores {"{{ variable }}"}.
            El archivo será validado automáticamente antes de subirlo.
          </DialogDescription>
        </DialogHeader>

        {/* FILE SELECT */}
        {step === "select" && (
          <div className="py-4">
            <div
              {...getRootProps()}
              className={`flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed p-10 transition-all ${
                isDragActive
                  ? "border-[#004ac6] bg-[#dbe1ff]/30"
                  : "border-[rgba(195,198,215,0.4)] hover:border-[#2563eb]/50 hover:bg-[#f7f9fb]"
              }`}
            >
              <input {...getInputProps()} />
              <UploadIcon className="size-10 text-[#434655] mb-3" />
              <p className="text-sm text-[#434655] text-center">
                {isDragActive
                  ? "Suelte el archivo aquí"
                  : "Arrastre y suelte un archivo .docx, o haga clic para seleccionar"}
              </p>
            </div>
          </div>
        )}

        {/* VALIDATING */}
        {step === "validating" && (
          <div className="flex flex-col items-center gap-3 py-8">
            <LoaderCircleIcon className="size-8 text-muted-foreground animate-spin" />
            <p className="text-sm text-muted-foreground">
              Validando plantilla...
            </p>
          </div>
        )}

        {/* VALID — show variables + upload form */}
        {step === "valid" && validation && (
          <form onSubmit={handleSubmit}>
            <div className="grid gap-4 py-4">
              <div className="flex items-center gap-2 rounded-lg border-0 bg-[#d1fae5] p-3">
                <CircleCheckIcon className="size-4 text-[#059669] shrink-0" />
                <p className="font-medium text-[#065f46] text-sm">
                  Plantilla válida — {validation.variable_summary.length} variable(s)
                  detectada(s)
                </p>
              </div>

              {/* Variables table */}
              {validation.variable_summary.length > 0 && (
                <ExpandableVariablesTable variables={validation.variable_summary} />
              )}

              {/* Warnings table (non-blocking) */}
              {validation.warnings.length > 0 && (
                <div>
                  <div className="flex items-center gap-2 mb-2 rounded-lg bg-amber-50 p-3">
                    <CircleAlertIcon className="size-4 text-amber-600 shrink-0" />
                    <p className="font-medium text-amber-700 text-sm">
                      {validation.warnings.length} advertencia(s) (no bloquean la subida)
                    </p>
                  </div>
                  <IssuesTable issues={validation.warnings} variableSummary={validation.variable_summary} />
                </div>
              )}

              {file && (
                <div className="flex items-center gap-2 rounded-lg border border-input p-3">
                  <FileIcon className="size-4 text-muted-foreground" />
                  <span className="flex-1 truncate text-sm">{file.name}</span>
                  <span className="text-xs text-muted-foreground">
                    {(file.size / 1024).toFixed(1)} KB
                  </span>
                  <button
                    type="button"
                    onClick={handleReset}
                    className="text-muted-foreground hover:text-foreground"
                  >
                    <XIcon className="size-4" />
                  </button>
                </div>
              )}

              <div className="grid gap-2">
                <Label htmlFor="template-name">Nombre *</Label>
                <Input
                  id="template-name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Ej. Contrato de Trabajo"
                  required
                />
              </div>

              <div className="grid gap-2">
                <Label htmlFor="template-description">Descripción</Label>
                <Textarea
                  id="template-description"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Descripción opcional de esta plantilla"
                  rows={3}
                />
              </div>
            </div>

            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  handleReset();
                  setOpen(false);
                }}
              >
                Cancelar
              </Button>
              <Button type="submit" disabled={uploadMutation.isPending}>
                {uploadMutation.isPending ? "Subiendo..." : "Subir"}
              </Button>
            </DialogFooter>
          </form>
        )}

        {/* ERRORS — show error list + actions */}
        {step === "errors" && validation && (
          <div className="space-y-4 py-4">
            {/* Errors table */}
            <div>
              <div className="flex items-center gap-2 mb-2 rounded-lg bg-[#ffdad6] p-3">
                <CircleAlertIcon className="size-4 text-[#ba1a1a] shrink-0" />
                <p className="font-medium text-[#93000a] text-sm">
                  {validation.errors.length} error(es) — deben corregirse antes de subir
                </p>
              </div>
              <IssuesTable issues={validation.errors} variableSummary={validation.variable_summary} />
            </div>

            {/* Warnings table */}
            {validation.warnings.length > 0 && (
              <div>
                <div className="flex items-center gap-2 mb-2 rounded-lg bg-amber-50 p-3">
                  <CircleAlertIcon className="size-4 text-amber-600 shrink-0" />
                  <p className="font-medium text-amber-700 text-sm">
                    {validation.warnings.length} advertencia(s)
                  </p>
                </div>
                <IssuesTable issues={validation.warnings} variableSummary={validation.variable_summary} />
              </div>
            )}

            {/* Variables summary table */}
            {validation.variable_summary.length > 0 && (
              <div>
                <p className="text-sm font-medium mb-2">
                  Variables detectadas ({validation.variable_summary.length}):
                </p>
                <ExpandableVariablesTable variables={validation.variable_summary} />
              </div>
            )}

            <div className="flex flex-wrap gap-2">
              {validation.has_fixable_errors &&
                !validation.has_unfixable_errors && (
                  <Button
                    onClick={handleAutoFix}
                    disabled={autoFixMutation.isPending}
                  >
                    <WrenchIcon className="size-4 mr-2" />
                    {autoFixMutation.isPending
                      ? "Corrigiendo..."
                      : "Auto-corregir y Descargar"}
                  </Button>
                )}
              {validation.has_fixable_errors &&
                validation.has_unfixable_errors && (
                  <Button
                    onClick={handleAutoFix}
                    variant="outline"
                    disabled={autoFixMutation.isPending}
                  >
                    <WrenchIcon className="size-4 mr-2" />
                    {autoFixMutation.isPending
                      ? "Corrigiendo..."
                      : "Descargar con correcciones parciales"}
                  </Button>
                )}
              <Button variant="outline" onClick={handleReset}>
                Seleccionar otro archivo
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

/** Highlights {{ variable_name }} patterns inside a context string. */
function HighlightedContext({ text, variableName }: { text: string; variableName: string }) {
  // Match {{ variableName }} with optional whitespace variations
  const pattern = new RegExp(
    `(\\{\\{\\s*${variableName.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\s*\\}\\})`,
    "gi"
  );
  const parts = text.split(pattern);

  return (
    <span>
      {parts.map((part, idx) =>
        pattern.test(part) ? (
          <span
            key={idx}
            className="bg-blue-100 text-blue-800 font-medium px-1 rounded font-mono"
          >
            {part}
          </span>
        ) : (
          <span key={idx}>{part}</span>
        )
      )}
    </span>
  );
}

function ExpandableVariablesTable({ variables }: { variables: VariableSummary[] }) {
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());

  function toggleRow(name: string) {
    setExpandedRows((prev) => {
      const next = new Set(prev);
      if (next.has(name)) {
        next.delete(name);
      } else {
        next.add(name);
      }
      return next;
    });
  }

  return (
    <div className="rounded-lg overflow-hidden max-h-64 overflow-y-auto bg-white shadow-[0_2px_8px_rgba(25,28,30,0.04)]">
      <table className="w-full text-sm">
        <thead className="bg-[#eceef0] sticky top-0">
          <tr>
            {/* chevron column */}
            <th className="w-6" />
            <th className="px-3 py-2 text-left font-semibold text-[#191c1e]">Variable</th>
            <th className="px-3 py-2 text-center font-semibold text-[#191c1e] w-16">Usos</th>
            <th className="px-3 py-2 text-center font-semibold text-[#191c1e] w-20">Estado</th>
          </tr>
        </thead>
        <tbody>
          {variables.map((v, i) => {
            const isExpanded = expandedRows.has(v.name);
            const rowBg = i % 2 === 1 ? "bg-[#f7f9fb]" : "";

            return (
              <Fragment key={v.name}>
                <tr
                  className={`border-t border-[rgba(195,198,215,0.15)] cursor-pointer select-none hover:bg-[#f0f2f5] transition-colors ${rowBg}`}
                  onClick={() => toggleRow(v.name)}
                >
                  {/* chevron */}
                  <td className="pl-2 pr-0 py-1.5 text-[#434655]/50">
                    <ChevronRightIcon
                      className={`size-3.5 transition-transform duration-150 ${isExpanded ? "rotate-90" : ""}`}
                    />
                  </td>
                  <td className="px-3 py-1.5 font-mono text-xs">
                    {"{{ "}
                    {v.name}
                    {" }}"}
                  </td>
                  <td className="px-3 py-1.5 text-center">{v.count}</td>
                  <td className="px-3 py-1.5 text-center">
                    <Badge
                      className={
                        v.has_errors
                          ? "bg-[#ffdad6] text-[#ba1a1a] border-0 rounded-full text-xs"
                          : "bg-[#d1fae5] text-[#059669] border-0 rounded-full text-xs"
                      }
                    >
                      {v.has_errors ? "Error" : "OK"}
                    </Badge>
                  </td>
                </tr>

                {isExpanded && (
                  <tr className={`border-t border-[rgba(195,198,215,0.08)] ${rowBg}`}>
                    {/* empty chevron cell */}
                    <td />
                    <td colSpan={3} className="px-3 pb-3 pt-1">
                      {v.contexts && v.contexts.length > 0 ? (
                        <div className="flex flex-col gap-1.5">
                          {v.contexts.map((ctx, ctxIdx) => (
                            <p
                              key={ctxIdx}
                              className="text-xs text-[#434655]/70 bg-[#f7f9fb] border-l-2 border-[#c3c6d7]/40 pl-2 py-1 pr-2 rounded-r-sm leading-relaxed"
                            >
                              <HighlightedContext text={ctx} variableName={v.name} />
                            </p>
                          ))}
                        </div>
                      ) : (
                        <p className="text-xs text-[#434655]/40 italic">
                          Sin contexto disponible
                        </p>
                      )}
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function IssuesTable({
  issues,
  variableSummary = [],
}: {
  issues: ValidationError[];
  variableSummary?: VariableSummary[];
}) {
  const [expandedRows, setExpandedRows] = useState<Set<number>>(new Set());

  function toggleRow(idx: number) {
    setExpandedRows((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) {
        next.delete(idx);
      } else {
        next.add(idx);
      }
      return next;
    });
  }

  /** Find contexts for a given variable name from the summary. */
  function getContexts(variableName: string | null): string[] {
    if (!variableName) return [];
    const summary = variableSummary.find((v) => v.name === variableName);
    return summary?.contexts ?? [];
  }

  return (
    <div className="rounded-lg overflow-hidden max-h-64 overflow-y-auto bg-white shadow-[0_2px_8px_rgba(25,28,30,0.04)]">
      <table className="w-full text-sm">
        <thead className="bg-[#eceef0] sticky top-0">
          <tr>
            <th className="w-6" />
            <th className="px-3 py-2 text-left font-semibold text-[#191c1e] w-20">Tipo</th>
            <th className="px-3 py-2 text-left font-semibold text-[#191c1e]">Variable</th>
            <th className="px-3 py-2 text-left font-semibold text-[#191c1e]">Detalle</th>
          </tr>
        </thead>
        <tbody>
          {issues.map((issue, i) => {
            const contexts = getContexts(issue.variable);
            const hasContext = contexts.length > 0;
            const isExpanded = expandedRows.has(i);
            const rowBg = i % 2 === 1 ? "bg-[#f7f9fb]" : "";

            return (
              <Fragment key={i}>
                <tr
                  className={`border-t border-[rgba(195,198,215,0.15)] ${hasContext ? "cursor-pointer hover:bg-[#f0f2f5] transition-colors" : ""} ${rowBg}`}
                  onClick={() => hasContext && toggleRow(i)}
                >
                  <td className="pl-2 pr-0 py-1.5 text-[#434655]/50">
                    {hasContext && (
                      <ChevronRightIcon
                        className={`size-3.5 transition-transform duration-150 ${isExpanded ? "rotate-90" : ""}`}
                      />
                    )}
                  </td>
                  <td className="px-3 py-1.5">
                    <Badge
                      className={
                        issue.fixable
                          ? "border-[#2563eb]/30 text-[#004ac6] bg-transparent rounded-full text-xs"
                          : "bg-[#ffdad6] text-[#ba1a1a] border-0 rounded-full text-xs"
                      }
                    >
                      {issue.fixable ? "Auto" : "Manual"}
                    </Badge>
                  </td>
                  <td className="px-3 py-1.5 font-mono text-xs">
                    {issue.variable || "—"}
                  </td>
                  <td className="px-3 py-1.5 text-[#434655]">
                    <span>{issue.message}</span>
                    {issue.suggestion && (
                      <span className="block text-xs mt-0.5 opacity-70">
                        Sugerencia: <span className="font-mono">{issue.suggestion}</span>
                      </span>
                    )}
                  </td>
                </tr>

                {isExpanded && hasContext && (
                  <tr className={`border-t border-[rgba(195,198,215,0.08)] ${rowBg}`}>
                    <td />
                    <td colSpan={3} className="px-3 pb-3 pt-1">
                      <div className="flex flex-col gap-1.5">
                        {contexts.map((ctx, ctxIdx) => (
                          <p
                            key={ctxIdx}
                            className="text-xs text-[#434655]/70 bg-[#f7f9fb] border-l-2 border-[#c3c6d7]/40 pl-2 py-1 pr-2 rounded-r-sm leading-relaxed"
                          >
                            {issue.variable ? (
                              <HighlightedContext text={ctx} variableName={issue.variable} />
                            ) : (
                              ctx
                            )}
                          </p>
                        ))}
                      </div>
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
