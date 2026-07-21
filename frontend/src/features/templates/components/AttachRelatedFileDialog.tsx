import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { useNavigate } from "@tanstack/react-router";
import { toast } from "sonner";
import {
  CircleAlert,
  File as FileIcon,
  Paperclip,
  ScanText,
  Upload,
  X,
} from "lucide-react";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

import { useAttachVersionFile } from "../api/mutations";

const MAX_LABEL_LENGTH = 120;

interface AttachRelatedFileDialogProps {
  templateId: string;
  /** Must be the template's CURRENT version — the backend rejects any other. */
  versionId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

interface AttachErrorInfo {
  message: string;
  issues: string[];
}

/**
 * Maps the attach endpoint's error contract to inline-renderable copy:
 * - 409 (duplicate label / not current version) and 400 (bad docx) carry a
 *   Spanish `detail` string.
 * - 422 carries `{ message, validation }` (same shape as template upload) —
 *   surface the message plus each validation error's message.
 */
function parseAttachError(error: unknown): AttachErrorInfo {
  const data = (
    error as { response?: { data?: unknown } } | null | undefined
  )?.response?.data as
    | {
        detail?: unknown;
        message?: unknown;
        validation?: { errors?: Array<{ message?: unknown }> };
      }
    | undefined;

  if (typeof data?.detail === "string") {
    return { message: data.detail, issues: [] };
  }
  if (typeof data?.message === "string") {
    const issues = (data.validation?.errors ?? [])
      .map((e) => (typeof e?.message === "string" ? e.message : null))
      .filter((m): m is string => m !== null);
    return { message: data.message, issues };
  }
  return { message: "Error al agregar el documento relacionado", issues: [] };
}

/**
 * Attach a related .docx to the template's current version. The file shares
 * the version's variable set and is generated alongside the primary document
 * on every generate call.
 */
export function AttachRelatedFileDialog({
  templateId,
  versionId,
  open,
  onOpenChange,
}: AttachRelatedFileDialogProps) {
  const [file, setFile] = useState<File | null>(null);
  const [label, setLabel] = useState("");
  const [error, setError] = useState<AttachErrorInfo | null>(null);

  const navigate = useNavigate();
  const attachMutation = useAttachVersionFile();

  const onDrop = useCallback((acceptedFiles: File[]) => {
    if (acceptedFiles.length > 0) {
      setFile(acceptedFiles[0]);
      setError(null);
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

  const trimmedLabel = label.trim();
  const labelTooLong = trimmedLabel.length > MAX_LABEL_LENGTH;
  const canSubmit =
    !!file && trimmedLabel.length > 0 && !labelTooLong && !attachMutation.isPending;

  function reset() {
    setFile(null);
    setLabel("");
    setError(null);
  }

  function handleOpenChange(isOpen: boolean) {
    onOpenChange(isOpen);
    if (!isOpen) reset();
  }

  function handleGoToExample() {
    // Alternate path: mark variables over a real filled document instead of
    // uploading a ready-made template. Full-page flow — close the dialog.
    handleOpenChange(false);
    navigate({
      to: "/templates/$templateId/attach-example",
      params: { templateId },
    });
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit || !file) return;

    setError(null);
    attachMutation.mutate(
      { templateId, versionId, file, label: trimmedLabel },
      {
        onSuccess: () => {
          toast.success("Documento relacionado agregado");
          reset();
          onOpenChange(false);
        },
        onError: (err: unknown) => {
          setError(parseAttachError(err));
        },
      },
    );
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-md">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle className="text-xl font-bold tracking-tight">
              Agregar documento relacionado
            </DialogTitle>
            <DialogDescription>
              Suba un .docx que use las mismas variables. Se generará junto al
              documento principal en cada generación.
            </DialogDescription>
          </DialogHeader>

          <div className="flex flex-col gap-4 py-4">
            {file ? (
              <div className="flex items-center gap-2 rounded-lg bg-[var(--bg-page)] px-3 py-2.5 ring-1 ring-[rgba(195,198,215,0.30)]">
                <FileIcon className="size-4 text-[var(--primary)]" />
                <span className="flex-1 truncate text-sm text-[var(--fg-1)]">
                  {file.name}
                </span>
                <span className="text-xs text-[var(--fg-3)]">
                  {(file.size / 1024).toFixed(1)} KB
                </span>
                <button
                  type="button"
                  onClick={() => setFile(null)}
                  className="rounded-md p-1 text-[var(--fg-3)] transition-colors hover:bg-[var(--bg-muted)] hover:text-[var(--fg-1)]"
                  aria-label="Quitar archivo"
                >
                  <X className="size-4" />
                </button>
              </div>
            ) : (
              <>
                <div
                  {...getRootProps()}
                  className={`flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed p-10 text-center transition-all ${
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

                {/* Alternate path — build the related file from a real
                    filled document, marking its variables visually. */}
                <div className="flex items-center gap-3">
                  <span className="h-px flex-1 bg-[rgba(195,198,215,0.30)]" />
                  <span className="text-[11px] font-medium uppercase tracking-[0.04em] text-[var(--fg-3)]">
                    o
                  </span>
                  <span className="h-px flex-1 bg-[rgba(195,198,215,0.30)]" />
                </div>
                <Button
                  type="button"
                  variant="outline"
                  onClick={handleGoToExample}
                  className="w-full"
                >
                  <ScanText className="mr-2 size-4 text-[var(--primary)]" />
                  Crear desde documento ejemplo
                </Button>
                <p className="-mt-2 text-center text-[11px] text-[var(--fg-3)]">
                  Suba un documento real ya completado y marque los textos que
                  serán variables.
                </p>
              </>
            )}

            <div className="grid gap-1.5">
              <Label
                htmlFor="related-file-label"
                className="text-xs font-semibold uppercase tracking-[0.04em] text-[var(--fg-3)]"
              >
                Etiqueta <span className="text-[var(--destructive)]">*</span>
              </Label>
              <Input
                id="related-file-label"
                value={label}
                onChange={(e) => {
                  setLabel(e.target.value);
                  setError(null);
                }}
                placeholder="Ej. Recibo de pago"
              />
              {labelTooLong ? (
                <p className="text-[11px] text-[#93000a]">
                  La etiqueta no puede superar los {MAX_LABEL_LENGTH}{" "}
                  caracteres.
                </p>
              ) : (
                <p className="text-[11px] text-[var(--fg-3)]">
                  Identifica este documento en las pestañas del editor y en el
                  nombre del archivo generado.
                </p>
              )}
            </div>

            {error && (
              <div className="flex items-start gap-2.5 rounded-[10px] bg-[#ffdad6] px-3.5 py-3 text-[13px] leading-[1.45] text-[#93000a]">
                <CircleAlert className="mt-px size-4 shrink-0 text-[var(--destructive)]" />
                <div className="flex-1">
                  <div>{error.message}</div>
                  {error.issues.length > 0 && (
                    <ul className="m-0 mt-1.5 list-disc pl-4">
                      {error.issues.map((issue, i) => (
                        <li key={i}>{issue}</li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>
            )}
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => handleOpenChange(false)}
            >
              Cancelar
            </Button>
            <Button
              type="submit"
              disabled={!canSubmit}
              className="bg-gradient-to-br from-[#004ac6] to-[#2563eb] font-semibold text-white shadow-[var(--shadow-brand-sm)] hover:shadow-[var(--shadow-brand-md)] disabled:opacity-60"
            >
              <Paperclip className="mr-2 size-4" />
              {attachMutation.isPending ? "Agregando…" : "Agregar documento"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
