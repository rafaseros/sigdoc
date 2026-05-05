import { Fragment, useState } from "react";
import { useDropzone } from "react-dropzone";
import { toast } from "sonner";
import { useQuery } from "@tanstack/react-query";
import {
  Check,
  CircleAlert,
  CircleCheck,
  Download,
  FileSpreadsheet,
  Sparkles,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { useDownloadExcelTemplate, useBulkGenerate } from "../api/mutations";
import { apiClient } from "@/shared/lib/api-client";
import { useAuth } from "@/shared/lib/auth";
import { BulkDownloadControls } from "./BulkDownloadControls";

interface BulkLimitsResponse {
  effective_bulk_limit: number | null;
}

function useBulkLimits() {
  return useQuery({
    queryKey: ["auth", "me", "bulk-limits"],
    queryFn: async () => {
      const { data } = await apiClient.get<BulkLimitsResponse>("/auth/me");
      return data;
    },
  });
}

interface BulkGenerateFlowProps {
  templateVersionId: string;
  templateName: string;
  variableCount: number;
}

const STEP_LABELS = [
  "Descargar plantilla",
  "Subir Excel",
  "Generar documentos",
  "Resultados",
];

export function BulkGenerateFlow({
  templateVersionId,
  templateName,
  variableCount,
}: BulkGenerateFlowProps) {
  const [step, setStep] = useState(1);
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<{
    batch_id: string;
    document_count: number;
    download_url: string;
    errors: Array<{ row: number; error: string }>;
  } | null>(null);

  const downloadExcel = useDownloadExcelTemplate();
  const bulkGenerate = useBulkGenerate();
  const { user } = useAuth();
  const { data: bulkLimits } = useBulkLimits();
  const effectiveBulkLimit = bulkLimits?.effective_bulk_limit ?? null;
  const isAdmin = user?.role === "admin";

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    accept: {
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [
        ".xlsx",
      ],
    },
    maxFiles: 1,
    onDrop: (accepted) => {
      if (accepted.length > 0) {
        setFile(accepted[0]);
        setStep(3);
      }
    },
  });

  const handleDownloadExcel = async () => {
    try {
      await downloadExcel.mutateAsync(templateVersionId);
      toast.success("¡Plantilla Excel descargada!");
      setStep(2);
    } catch {
      toast.error("Error al descargar la plantilla Excel");
    }
  };

  const handleGenerate = async () => {
    if (!file) return;
    try {
      const res = await bulkGenerate.mutateAsync({
        templateVersionId,
        file,
      });
      setResult(res);
      setStep(4);
      toast.success(`¡Se generaron ${res.document_count} documentos!`);
    } catch (err: unknown) {
      const detail =
        err &&
        typeof err === "object" &&
        "response" in err &&
        (err as { response?: { data?: { detail?: string } } }).response?.data
          ?.detail;
      toast.error((detail as string) || "Error al generar los documentos");
    }
  };

  return (
    <div className="space-y-5">
      {/* ── Visual stepper ── */}
      <div className="rounded-xl bg-white p-4 shadow-[var(--shadow-sm)] ring-1 ring-[rgba(195,198,215,0.30)]">
        <div className="flex items-center">
          {STEP_LABELS.map((label, i) => {
            const idx = i + 1;
            const isDone = idx < step;
            const isActive = idx === step;
            return (
              <Fragment key={label}>
                <div className="flex min-w-0 flex-1 items-center gap-2.5">
                  <span
                    className={`inline-flex size-8 shrink-0 items-center justify-center rounded-full text-[12px] font-bold transition-all ${
                      isDone
                        ? "bg-[#d1fae5] text-[#059669]"
                        : isActive
                        ? "bg-gradient-to-br from-[#004ac6] to-[#2563eb] text-white shadow-[var(--shadow-brand-sm)]"
                        : "bg-[var(--bg-muted)] text-[var(--fg-3)]"
                    }`}
                  >
                    {isDone ? <Check className="size-4" /> : idx}
                  </span>
                  <span
                    className={`hidden truncate text-[12.5px] font-medium sm:inline ${
                      isActive
                        ? "text-[var(--fg-1)]"
                        : isDone
                        ? "text-[var(--fg-2)]"
                        : "text-[var(--fg-3)]"
                    }`}
                  >
                    {label}
                  </span>
                </div>
                {i < STEP_LABELS.length - 1 && (
                  <div
                    className={`mx-2 hidden h-[2px] flex-1 rounded-full transition-all sm:block ${
                      isDone
                        ? "bg-gradient-to-r from-[#004ac6] to-[#2563eb]"
                        : "bg-[var(--bg-muted)]"
                    }`}
                  />
                )}
              </Fragment>
            );
          })}
        </div>
      </div>

      {/* ── Step 1: Download Excel ── */}
      {step >= 1 && (
        <div
          className={`rounded-xl bg-white p-5 shadow-[var(--shadow-sm)] ring-1 ring-[rgba(195,198,215,0.30)] transition-opacity ${
            step === 1 ? "" : "opacity-70"
          }`}
        >
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-start gap-3">
              <span
                className={`inline-flex size-10 shrink-0 items-center justify-center rounded-xl ${
                  step > 1
                    ? "bg-[#d1fae5] text-[#059669]"
                    : "bg-[var(--bg-accent)] text-[var(--primary)]"
                }`}
              >
                {step > 1 ? (
                  <Check className="size-5" />
                ) : (
                  <Download className="size-5" />
                )}
              </span>
              <div>
                <h3 className="m-0 text-[15px] font-bold tracking-tight text-[var(--fg-1)]">
                  Paso 1 — Descargar plantilla Excel
                </h3>
                <p className="mt-1 text-[13px] text-[var(--fg-3)]">
                  Archivo con {variableCount} columna
                  {variableCount === 1 ? "" : "s"} — una por variable. Complete
                  cada fila con los datos de un documento.
                  {effectiveBulkLimit !== null && (
                    <>
                      {" "}
                      <span className="font-semibold text-[var(--fg-2)]">
                        Máximo {effectiveBulkLimit} documentos por lote.
                      </span>
                    </>
                  )}
                </p>
              </div>
            </div>
            <Button
              onClick={handleDownloadExcel}
              disabled={downloadExcel.isPending}
              variant={step > 1 ? "outline" : "default"}
              className={
                step > 1
                  ? "border-[rgba(195,198,215,0.30)] text-[var(--fg-2)] hover:bg-[var(--bg-accent)]/50 hover:text-[var(--primary)]"
                  : "bg-gradient-to-br from-[#004ac6] to-[#2563eb] font-semibold text-white shadow-[var(--shadow-brand-sm)] hover:shadow-[var(--shadow-brand-md)]"
              }
            >
              <Download className="size-4" />
              {downloadExcel.isPending
                ? "Descargando..."
                : step > 1
                ? "Volver a descargar"
                : "Descargar plantilla"}
            </Button>
          </div>
        </div>
      )}

      {/* ── Step 2: Upload filled Excel ── */}
      {step >= 2 && (
        <div
          className={`rounded-xl bg-white p-5 shadow-[var(--shadow-sm)] ring-1 ring-[rgba(195,198,215,0.30)] transition-opacity ${
            step === 2 ? "" : step > 2 ? "opacity-70" : ""
          }`}
        >
          <div className="mb-4 flex items-start gap-3">
            <span
              className={`inline-flex size-10 shrink-0 items-center justify-center rounded-xl ${
                step > 2
                  ? "bg-[#d1fae5] text-[#059669]"
                  : "bg-gradient-to-br from-[#004ac6] to-[#2563eb] text-white shadow-[var(--shadow-brand-sm)]"
              }`}
            >
              {step > 2 ? (
                <Check className="size-5" />
              ) : (
                <FileSpreadsheet className="size-5" />
              )}
            </span>
            <div>
              <h3 className="m-0 text-[15px] font-bold tracking-tight text-[var(--fg-1)]">
                Paso 2 — Subir Excel completado
              </h3>
              <p className="mt-1 text-[13px] text-[var(--fg-3)]">
                Arrastre el archivo .xlsx o haga clic para buscar.
              </p>
            </div>
          </div>

          {file && step > 2 ? (
            <div className="flex flex-wrap items-center gap-3 rounded-[10px] bg-[#d1fae5] px-3.5 py-3 text-[13px] text-[#065f46]">
              <FileSpreadsheet className="size-5 shrink-0 text-[#059669]" />
              <div className="min-w-0 flex-1">
                <strong className="truncate">{file.name}</strong>{" "}
                <span className="text-[#047857]">
                  · {(file.size / 1024).toFixed(1)} KB
                </span>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setFile(null);
                  setStep(2);
                }}
                className="text-[#065f46] hover:bg-[#a7f3d0]/40 hover:text-[#065f46]"
              >
                Cambiar archivo
              </Button>
            </div>
          ) : (
            <div
              {...getRootProps()}
              className={`flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed p-10 text-center transition-all ${
                isDragActive
                  ? "border-[#004ac6] bg-[var(--bg-accent)]/50"
                  : "border-[rgba(195,198,215,0.50)] bg-[var(--bg-page)] hover:border-[#2563eb]/50 hover:bg-[var(--bg-accent)]/30"
              }`}
            >
              <input {...getInputProps()} />
              <FileSpreadsheet
                className={`size-9 ${
                  isDragActive ? "text-[#004ac6]" : "text-[var(--fg-3)]"
                }`}
              />
              {file ? (
                <p className="text-[13px] text-[var(--fg-1)]">
                  Seleccionado:{" "}
                  <strong className="font-semibold">{file.name}</strong>{" "}
                  <span className="text-[var(--fg-3)]">
                    ({(file.size / 1024).toFixed(1)} KB)
                  </span>
                </p>
              ) : isDragActive ? (
                <p className="text-[14px] font-medium text-[#004ac6]">
                  Suelte el archivo Excel aquí
                </p>
              ) : (
                <>
                  <p className="text-[14px] font-medium text-[var(--fg-1)]">
                    Arrastre y suelte el archivo .xlsx
                  </p>
                  <p className="text-[12px] text-[var(--fg-3)]">
                    o haga clic para buscar
                  </p>
                </>
              )}
            </div>
          )}
        </div>
      )}

      {/* ── Step 3: Confirm & Generate ── */}
      {step >= 3 && !result && (
        <div className="rounded-xl bg-white p-5 shadow-[var(--shadow-sm)] ring-1 ring-[rgba(195,198,215,0.30)]">
          <div className="mb-4 flex items-start gap-3">
            <span className="inline-flex size-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-[#004ac6] to-[#2563eb] text-white shadow-[var(--shadow-brand-sm)]">
              <Sparkles className="size-5" />
            </span>
            <div>
              <h3 className="m-0 text-[15px] font-bold tracking-tight text-[var(--fg-1)]">
                Paso 3 — Revisar y generar
              </h3>
              <p className="mt-1 text-[13px] text-[var(--fg-3)]">
                Verifique los datos antes de generar el lote completo.
              </p>
            </div>
          </div>

          <div className="mb-4 flex items-center gap-2 rounded-[10px] bg-[#d1fae5] px-3.5 py-3 text-[13px] leading-[1.45] text-[#065f46]">
            <CircleCheck className="size-4 shrink-0 text-[#059669]" />
            <span>
              <strong>Listo para generar</strong> — desde &quot;{file?.name}
              &quot; usando la plantilla &quot;{templateName}&quot;.
            </span>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-2">
            <Button
              variant="outline"
              onClick={() => {
                setFile(null);
                setStep(2);
              }}
              className="border-[rgba(195,198,215,0.30)] text-[var(--fg-2)]"
            >
              Volver a subir
            </Button>
            <Button
              onClick={handleGenerate}
              disabled={bulkGenerate.isPending}
              className="bg-gradient-to-br from-[#004ac6] to-[#2563eb] font-semibold text-white shadow-[var(--shadow-brand-sm)] hover:shadow-[var(--shadow-brand-md)]"
            >
              <Sparkles className="size-4" />
              {bulkGenerate.isPending
                ? "Generando..."
                : "Generar documentos"}
            </Button>
          </div>
        </div>
      )}

      {/* ── Step 4: Results ── */}
      {result && (
        <div className="rounded-xl bg-white p-5 shadow-[var(--shadow-sm)] ring-1 ring-[rgba(195,198,215,0.30)]">
          <div className="mb-4 flex items-start gap-3">
            <span className="inline-flex size-10 shrink-0 items-center justify-center rounded-xl bg-[#d1fae5] text-[#059669]">
              <Check className="size-5" />
            </span>
            <div>
              <h3 className="m-0 text-[15px] font-bold tracking-tight text-[var(--fg-1)]">
                Paso 4 — Resultados
              </h3>
              <p className="mt-1 text-[13px] text-[var(--fg-3)]">
                Lote completado. Descargue los documentos generados.
              </p>
            </div>
          </div>

          <div className="space-y-3">
            <div className="flex items-center gap-2 rounded-[10px] bg-[#d1fae5] px-3.5 py-3 text-[13px] leading-[1.45] text-[#065f46]">
              <CircleCheck className="size-4 shrink-0 text-[#059669]" />
              <span>
                Se generaron <strong>{result.document_count}</strong> documento
                {result.document_count === 1 ? "" : "s"} con éxito.
              </span>
            </div>
            {result.errors.length > 0 && (
              <div className="flex items-start gap-2 rounded-[10px] bg-[#ffdad6] px-3.5 py-3 text-[13px] leading-[1.45] text-[#93000a]">
                <CircleAlert className="size-4 shrink-0 text-[var(--destructive)]" />
                <div>
                  <p className="m-0 font-semibold">Errores en algunas filas:</p>
                  <ul className="mt-1 list-disc pl-4">
                    {result.errors.map((e, i) => (
                      <li key={i}>
                        Fila {e.row}: {e.error}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            )}
            <div className="flex flex-wrap items-center justify-end gap-3 pt-1">
              <BulkDownloadControls
                batchId={result.batch_id}
                isAdmin={isAdmin ?? false}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
