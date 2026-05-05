import { useState, useCallback, Fragment } from "react";
import { useDropzone } from "react-dropzone";
import { toast } from "sonner";
import {
  Upload,
  File as FileIcon,
  X,
  LoaderCircle,
  CheckCircle2,
  AlertCircle,
  Wrench,
  ChevronRight,
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

  const onDrop = useCallback(
    async (acceptedFiles: File[]) => {
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
    },
    [validateMutation]
  );

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
      <DialogTrigger
        render={
          <Button className="bg-gradient-to-br from-[#004ac6] to-[#2563eb] font-semibold text-white shadow-[var(--shadow-brand-sm)] hover:shadow-[var(--shadow-brand-md)]" />
        }
      >
        <Upload className="mr-2 size-4" />
        Subir Plantilla
      </DialogTrigger>
      <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle className="text-xl font-bold tracking-tight">
            Subir nueva plantilla
          </DialogTitle>
          <DialogDescription>
            Suba un archivo .docx con marcadores tipo {"{{ variable }}"}. El
            archivo se valida automáticamente.
          </DialogDescription>
        </DialogHeader>

        {/* SELECT */}
        {step === "select" && (
          <div className="py-2">
            <div
              {...getRootProps()}
              className={`flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed p-12 text-center transition-all ${
                isDragActive
                  ? "border-[var(--primary)] bg-[var(--bg-accent)]/50"
                  : "border-[rgba(195,198,215,0.45)] bg-[var(--bg-page)] hover:border-[var(--ring)]/40 hover:bg-white"
              }`}
            >
              <input {...getInputProps()} />
              <Upload
                className={`size-8 ${isDragActive ? "text-[var(--primary)]" : "text-[var(--fg-3)]"}`}
              />
              <div className="text-sm font-semibold text-[var(--fg-1)]">
                {isDragActive
                  ? "Suelte aquí"
                  : "Arrastre y suelte un archivo .docx"}
              </div>
              <div className="text-xs text-[var(--fg-3)]">
                o haga clic para buscar · máx. 10 MB
              </div>
            </div>
          </div>
        )}

        {/* VALIDATING */}
        {step === "validating" && (
          <div className="flex flex-col items-center gap-3 py-10">
            <LoaderCircle className="size-7 animate-spin text-[var(--primary)]" />
            <p className="text-sm font-medium text-[var(--fg-1)]">
              Validando {file?.name ?? "plantilla"}…
            </p>
          </div>
        )}

        {/* VALID */}
        {step === "valid" && validation && (
          <form onSubmit={handleSubmit}>
            <div className="grid gap-4 py-2">
              <Banner variant="ok" icon={<CheckCircle2 className="size-4 shrink-0" />}>
                <strong className="font-semibold">Plantilla válida</strong> —{" "}
                {validation.variable_summary.length} variable
                {validation.variable_summary.length === 1 ? "" : "s"}{" "}
                detectada
                {validation.variable_summary.length === 1 ? "" : "s"}
              </Banner>

              {validation.variable_summary.length > 0 && (
                <ExpandableVariablesTable variables={validation.variable_summary} />
              )}

              {validation.warnings.length > 0 && (
                <div className="space-y-2">
                  <Banner variant="warn" icon={<AlertCircle className="size-4 shrink-0" />}>
                    {validation.warnings.length} advertencia
                    {validation.warnings.length === 1 ? "" : "s"} (no bloquean la subida)
                  </Banner>
                  <IssuesTable
                    issues={validation.warnings}
                    variableSummary={validation.variable_summary}
                  />
                </div>
              )}

              {file && <FilePill file={file} onClear={handleReset} />}

              <div className="grid gap-2 sm:grid-cols-2">
                <div className="grid gap-1.5">
                  <Label htmlFor="template-name" className="text-[12.5px] font-medium text-[var(--fg-2)]">
                    Nombre <span className="text-[var(--destructive)]">*</span>
                  </Label>
                  <Input
                    id="template-name"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="Ej. Contrato de Trabajo"
                    required
                  />
                </div>
                <div className="grid gap-1.5 sm:col-span-1">
                  <Label className="text-[12.5px] font-medium text-[var(--fg-2)]">
                    Variables detectadas
                  </Label>
                  <div className="flex h-9 items-center rounded-lg bg-[var(--bg-muted)] px-3 text-sm text-[var(--fg-2)]">
                    {validation.variable_summary.length}{" "}
                    {validation.variable_summary.length === 1 ? "variable" : "variables"}
                  </div>
                </div>
              </div>

              <div className="grid gap-1.5">
                <Label htmlFor="template-description" className="text-[12.5px] font-medium text-[var(--fg-2)]">
                  Descripción (opcional)
                </Label>
                <Textarea
                  id="template-description"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="¿Para qué se usa esta plantilla?"
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
              <Button
                type="submit"
                disabled={uploadMutation.isPending}
                className="bg-gradient-to-br from-[#004ac6] to-[#2563eb] font-semibold text-white shadow-[var(--shadow-brand-sm)] hover:shadow-[var(--shadow-brand-md)]"
              >
                <Upload className="mr-2 size-4" />
                {uploadMutation.isPending ? "Subiendo…" : "Subir Plantilla"}
              </Button>
            </DialogFooter>
          </form>
        )}

        {/* ERRORS */}
        {step === "errors" && validation && (
          <div className="space-y-4 py-2">
            <Banner variant="err" icon={<AlertCircle className="size-4 shrink-0" />}>
              <strong className="font-semibold">
                {validation.errors.length} error
                {validation.errors.length === 1 ? "" : "es"}
              </strong>{" "}
              — deben corregirse antes de subir.
            </Banner>
            <IssuesTable
              issues={validation.errors}
              variableSummary={validation.variable_summary}
            />

            {validation.warnings.length > 0 && (
              <div className="space-y-2">
                <Banner variant="warn" icon={<AlertCircle className="size-4 shrink-0" />}>
                  {validation.warnings.length} advertencia
                  {validation.warnings.length === 1 ? "" : "s"}
                </Banner>
                <IssuesTable
                  issues={validation.warnings}
                  variableSummary={validation.variable_summary}
                />
              </div>
            )}

            {validation.variable_summary.length > 0 && (
              <div className="space-y-2">
                <p className="text-sm font-medium text-[var(--fg-1)]">
                  Variables detectadas ({validation.variable_summary.length})
                </p>
                <ExpandableVariablesTable variables={validation.variable_summary} />
              </div>
            )}

            <div className="flex flex-wrap gap-2">
              {validation.has_fixable_errors && !validation.has_unfixable_errors && (
                <Button
                  onClick={handleAutoFix}
                  disabled={autoFixMutation.isPending}
                  className="bg-gradient-to-br from-[#004ac6] to-[#2563eb] font-semibold text-white shadow-[var(--shadow-brand-sm)] hover:shadow-[var(--shadow-brand-md)]"
                >
                  <Wrench className="mr-2 size-4" />
                  {autoFixMutation.isPending
                    ? "Corrigiendo…"
                    : "Auto-corregir y descargar"}
                </Button>
              )}
              {validation.has_fixable_errors && validation.has_unfixable_errors && (
                <Button
                  onClick={handleAutoFix}
                  variant="outline"
                  disabled={autoFixMutation.isPending}
                >
                  <Wrench className="mr-2 size-4" />
                  {autoFixMutation.isPending
                    ? "Corrigiendo…"
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

/* ---------- Sub-components ---------- */

function FilePill({ file, onClear }: { file: File; onClear: () => void }) {
  return (
    <div className="flex items-center gap-2 rounded-lg bg-[var(--bg-page)] px-3 py-2.5 ring-1 ring-[rgba(195,198,215,0.30)]">
      <FileIcon className="size-4 text-[var(--primary)]" />
      <span className="flex-1 truncate text-sm text-[var(--fg-1)]">{file.name}</span>
      <span className="text-xs text-[var(--fg-3)]">
        {(file.size / 1024).toFixed(1)} KB
      </span>
      <button
        type="button"
        onClick={onClear}
        className="rounded-md p-1 text-[var(--fg-3)] transition-colors hover:bg-[var(--bg-muted)] hover:text-[var(--fg-1)]"
        aria-label="Quitar archivo"
      >
        <X className="size-4" />
      </button>
    </div>
  );
}

function Banner({
  variant,
  icon,
  children,
}: {
  variant: "ok" | "warn" | "err";
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  const tones = {
    ok: "bg-[#d1fae5] text-[#065f46]",
    warn: "bg-[#fef3c7] text-[#78350f]",
    err: "bg-[#ffdad6] text-[#93000a]",
  };
  const iconColors = {
    ok: "text-[#059669]",
    warn: "text-[#b45309]",
    err: "text-[var(--destructive)]",
  };
  return (
    <div
      className={`flex items-start gap-2.5 rounded-[10px] px-3.5 py-3 text-[13px] leading-[1.45] ${tones[variant]}`}
    >
      <span className={`mt-px ${iconColors[variant]}`}>{icon}</span>
      <div className="flex-1">{children}</div>
    </div>
  );
}

/** Highlights {{ variable_name }} patterns inside a context string. */
function HighlightedContext({
  text,
  variableName,
}: {
  text: string;
  variableName: string;
}) {
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
            className="rounded bg-[var(--bg-accent)] px-1 font-mono font-medium text-[var(--primary)]"
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
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  }

  return (
    <div className="max-h-64 overflow-hidden overflow-y-auto rounded-lg bg-white ring-1 ring-[rgba(195,198,215,0.30)]">
      <table className="w-full text-sm">
        <thead className="sticky top-0 bg-[var(--muted)]">
          <tr>
            <th className="w-6" />
            <th className="px-3 py-2 text-left font-semibold text-[var(--fg-1)]">Variable</th>
            <th className="w-16 px-3 py-2 text-center font-semibold text-[var(--fg-1)]">Usos</th>
            <th className="w-20 px-3 py-2 text-center font-semibold text-[var(--fg-1)]">Estado</th>
          </tr>
        </thead>
        <tbody>
          {variables.map((v, i) => {
            const isExpanded = expandedRows.has(v.name);
            const rowBg = i % 2 === 1 ? "bg-[var(--bg-page)]" : "";
            return (
              <Fragment key={v.name}>
                <tr
                  className={`cursor-pointer select-none border-t border-[rgba(195,198,215,0.15)] transition-colors hover:bg-[var(--bg-muted)] ${rowBg}`}
                  onClick={() => toggleRow(v.name)}
                >
                  <td className="py-1.5 pl-2 pr-0 text-[var(--fg-3)]/60">
                    <ChevronRight
                      className={`size-3.5 transition-transform duration-150 ${
                        isExpanded ? "rotate-90" : ""
                      }`}
                    />
                  </td>
                  <td className="px-3 py-1.5 font-mono text-xs text-[var(--primary)]">
                    {"{{ "}
                    {v.name}
                    {" }}"}
                  </td>
                  <td className="px-3 py-1.5 text-center">{v.count}</td>
                  <td className="px-3 py-1.5 text-center">
                    <Badge
                      className={
                        v.has_errors
                          ? "rounded-full border-0 bg-[#ffdad6] text-[#93000a]"
                          : "rounded-full border-0 bg-[#d1fae5] text-[#065f46]"
                      }
                    >
                      {v.has_errors ? "Error" : "OK"}
                    </Badge>
                  </td>
                </tr>

                {isExpanded && (
                  <tr className={`border-t border-[rgba(195,198,215,0.08)] ${rowBg}`}>
                    <td />
                    <td colSpan={3} className="px-3 pb-3 pt-1">
                      {v.contexts && v.contexts.length > 0 ? (
                        <div className="flex flex-col gap-1.5">
                          {v.contexts.map((ctx, ctxIdx) => (
                            <p
                              key={ctxIdx}
                              className="rounded-r-sm border-l-2 border-[rgba(195,198,215,0.40)] bg-[var(--bg-page)] py-1 pl-2 pr-2 text-xs leading-relaxed text-[var(--fg-2)]"
                            >
                              <HighlightedContext text={ctx} variableName={v.name} />
                            </p>
                          ))}
                        </div>
                      ) : (
                        <p className="text-xs italic text-[var(--fg-3)]">
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
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  }

  function getContexts(variableName: string | null): string[] {
    if (!variableName) return [];
    const summary = variableSummary.find((v) => v.name === variableName);
    return summary?.contexts ?? [];
  }

  return (
    <div className="max-h-64 overflow-hidden overflow-y-auto rounded-lg bg-white ring-1 ring-[rgba(195,198,215,0.30)]">
      <table className="w-full text-sm">
        <thead className="sticky top-0 bg-[var(--muted)]">
          <tr>
            <th className="w-6" />
            <th className="w-20 px-3 py-2 text-left font-semibold text-[var(--fg-1)]">Tipo</th>
            <th className="px-3 py-2 text-left font-semibold text-[var(--fg-1)]">Variable</th>
            <th className="px-3 py-2 text-left font-semibold text-[var(--fg-1)]">Detalle</th>
          </tr>
        </thead>
        <tbody>
          {issues.map((issue, i) => {
            const contexts = getContexts(issue.variable);
            const hasContext = contexts.length > 0;
            const isExpanded = expandedRows.has(i);
            const rowBg = i % 2 === 1 ? "bg-[var(--bg-page)]" : "";
            return (
              <Fragment key={i}>
                <tr
                  className={`border-t border-[rgba(195,198,215,0.15)] ${
                    hasContext ? "cursor-pointer transition-colors hover:bg-[var(--bg-muted)]" : ""
                  } ${rowBg}`}
                  onClick={() => hasContext && toggleRow(i)}
                >
                  <td className="py-1.5 pl-2 pr-0 text-[var(--fg-3)]/60">
                    {hasContext && (
                      <ChevronRight
                        className={`size-3.5 transition-transform duration-150 ${
                          isExpanded ? "rotate-90" : ""
                        }`}
                      />
                    )}
                  </td>
                  <td className="px-3 py-1.5">
                    <Badge
                      className={
                        issue.fixable
                          ? "rounded-full border border-[rgba(37,99,235,0.30)] bg-transparent text-[var(--primary)]"
                          : "rounded-full border-0 bg-[#ffdad6] text-[#93000a]"
                      }
                    >
                      {issue.fixable ? "Auto" : "Manual"}
                    </Badge>
                  </td>
                  <td className="px-3 py-1.5 font-mono text-xs text-[var(--primary)]">
                    {issue.variable || "—"}
                  </td>
                  <td className="px-3 py-1.5 text-[var(--fg-2)]">
                    <span>{issue.message}</span>
                    {issue.suggestion && (
                      <span className="mt-0.5 block text-xs opacity-70">
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
                            className="rounded-r-sm border-l-2 border-[rgba(195,198,215,0.40)] bg-[var(--bg-page)] py-1 pl-2 pr-2 text-xs leading-relaxed text-[var(--fg-2)]"
                          >
                            {issue.variable ? (
                              <HighlightedContext
                                text={ctx}
                                variableName={issue.variable}
                              />
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
