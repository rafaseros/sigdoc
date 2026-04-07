import { useState, useCallback } from "react";
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
      <DialogContent className="sm:max-w-2xl max-h-[85vh] overflow-y-auto">
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
              className={`flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed p-8 transition-colors ${
                isDragActive
                  ? "border-ring bg-ring/5"
                  : "border-input hover:border-ring/50"
              }`}
            >
              <input {...getInputProps()} />
              <UploadIcon className="size-10 text-muted-foreground mb-3" />
              <p className="text-sm text-muted-foreground text-center">
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
              <div className="flex items-center gap-2 rounded-md border border-green-500/50 bg-green-500/5 p-3">
                <CircleCheckIcon className="size-4 text-green-600 dark:text-green-400 shrink-0" />
                <p className="font-medium text-green-700 dark:text-green-400 text-sm">
                  Plantilla válida — {validation.variable_summary.length} variable(s)
                  detectada(s)
                </p>
              </div>

              {/* Variables table */}
              {validation.variable_summary.length > 0 && (
                <VariablesTable variables={validation.variable_summary} />
              )}

              {/* Warnings table (non-blocking) */}
              {validation.warnings.length > 0 && (
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <CircleAlertIcon className="size-4 text-amber-600 dark:text-amber-400 shrink-0" />
                    <p className="font-medium text-amber-700 dark:text-amber-400 text-sm">
                      {validation.warnings.length} advertencia(s) (no bloquean la subida)
                    </p>
                  </div>
                  <IssuesTable issues={validation.warnings} />
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
              <div className="flex items-center gap-2 mb-2">
                <CircleAlertIcon className="size-4 text-destructive shrink-0" />
                <p className="font-medium text-destructive text-sm">
                  {validation.errors.length} error(es) — deben corregirse antes de subir
                </p>
              </div>
              <IssuesTable issues={validation.errors} />
            </div>

            {/* Warnings table */}
            {validation.warnings.length > 0 && (
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <CircleAlertIcon className="size-4 text-amber-600 dark:text-amber-400 shrink-0" />
                  <p className="font-medium text-amber-700 dark:text-amber-400 text-sm">
                    {validation.warnings.length} advertencia(s)
                  </p>
                </div>
                <IssuesTable issues={validation.warnings} />
              </div>
            )}

            {/* Variables summary table */}
            {validation.variable_summary.length > 0 && (
              <div>
                <p className="text-sm font-medium mb-2">
                  Variables detectadas ({validation.variable_summary.length}):
                </p>
                <VariablesTable variables={validation.variable_summary} />
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

function VariablesTable({ variables }: { variables: VariableSummary[] }) {
  return (
    <div className="rounded-md border overflow-hidden max-h-48 overflow-y-auto">
      <table className="w-full text-sm">
        <thead className="bg-muted sticky top-0">
          <tr>
            <th className="px-3 py-1.5 text-left font-medium">Variable</th>
            <th className="px-3 py-1.5 text-center font-medium w-16">Usos</th>
            <th className="px-3 py-1.5 text-center font-medium w-20">Estado</th>
          </tr>
        </thead>
        <tbody>
          {variables.map((v) => (
            <tr key={v.name} className="border-t">
              <td className="px-3 py-1.5 font-mono text-xs">
                {"{{ "}
                {v.name}
                {" }}"}
              </td>
              <td className="px-3 py-1.5 text-center">{v.count}</td>
              <td className="px-3 py-1.5 text-center">
                <Badge
                  variant={v.has_errors ? "destructive" : "secondary"}
                  className="text-xs"
                >
                  {v.has_errors ? "Error" : "OK"}
                </Badge>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function IssuesTable({ issues }: { issues: ValidationError[] }) {
  return (
    <div className="rounded-md border overflow-hidden max-h-48 overflow-y-auto">
      <table className="w-full text-sm">
        <thead className="bg-muted sticky top-0">
          <tr>
            <th className="px-3 py-1.5 text-left font-medium w-20">Tipo</th>
            <th className="px-3 py-1.5 text-left font-medium">Variable</th>
            <th className="px-3 py-1.5 text-left font-medium">Detalle</th>
          </tr>
        </thead>
        <tbody>
          {issues.map((issue, i) => (
            <tr key={i} className="border-t">
              <td className="px-3 py-1.5">
                <Badge
                  variant={issue.fixable ? "outline" : "destructive"}
                  className="text-xs"
                >
                  {issue.fixable ? "Auto" : "Manual"}
                </Badge>
              </td>
              <td className="px-3 py-1.5 font-mono text-xs">
                {issue.variable || "—"}
              </td>
              <td className="px-3 py-1.5 text-muted-foreground">
                <span>{issue.message}</span>
                {issue.suggestion && (
                  <span className="block text-xs mt-0.5 opacity-70">
                    Sugerencia: <span className="font-mono">{issue.suggestion}</span>
                  </span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
