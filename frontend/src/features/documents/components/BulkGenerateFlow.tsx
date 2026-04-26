import { useState } from "react";
import { useDropzone } from "react-dropzone";
import { toast } from "sonner";
import { useQuery } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
    <div className="space-y-6">
      {/* Step indicators */}
      <div className="flex gap-2">
        {[1, 2, 3, 4].map((s) => (
          <div
            key={s}
            className={`h-2 flex-1 rounded-full transition-all ${
              s < step ? "bg-gradient-to-r from-[#004ac6] to-[#2563eb]" : s === step ? "bg-[#2563eb]" : "bg-[#eceef0]"
            }`}
          />
        ))}
      </div>

      {/* Step 1: Download Excel */}
      {step >= 1 && (
        <Card className="border-0 bg-white shadow-[0_12px_32px_rgba(25,28,30,0.06)]">
          <CardHeader>
            <CardTitle className="text-base">
              Paso 1: Descargar Plantilla Excel
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-[#434655] mb-3">
              Descargue el archivo Excel con {variableCount} columnas de variables.
              Complete cada fila con los datos de cada documento.
              {effectiveBulkLimit !== null ? (
                <span className="ml-1">
                  <strong>Máximo de documentos: {effectiveBulkLimit}</strong>.
                </span>
              ) : null}
            </p>
            <Button
              onClick={handleDownloadExcel}
              disabled={downloadExcel.isPending}
              variant={step > 1 ? "outline" : "default"}
              className={step > 1 ? "border-[rgba(195,198,215,0.3)] hover:bg-[#dbe1ff]/50 hover:text-[#004ac6]" : "bg-gradient-to-br from-[#004ac6] to-[#2563eb] text-white shadow-[0_4px_12px_rgba(0,74,198,0.3)]"}
            >
              {downloadExcel.isPending
                ? "Descargando..."
                : "Descargar Plantilla Excel"}
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Step 2: Upload filled Excel */}
      {step >= 2 && (
        <Card className="border-0 bg-white shadow-[0_12px_32px_rgba(25,28,30,0.06)]">
          <CardHeader>
            <CardTitle className="text-base">
              Paso 2: Subir Excel Completado
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div
              {...getRootProps()}
              className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-all ${
                isDragActive
                  ? "border-[#004ac6] bg-[#dbe1ff]/30"
                  : "border-[rgba(195,198,215,0.4)] hover:border-[#2563eb]/50 hover:bg-[#f7f9fb]"
              }`}
            >
              <input {...getInputProps()} />
              {file ? (
                <p className="text-sm">
                  Seleccionado: <strong>{file.name}</strong> (
                  {(file.size / 1024).toFixed(1)} KB)
                </p>
              ) : isDragActive ? (
                <p className="text-sm">Suelte el archivo Excel aquí...</p>
              ) : (
                <p className="text-sm text-[#434655]">
                  Arrastre y suelte su archivo .xlsx completado, o haga clic para buscar
                </p>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Step 3: Confirm & Generate */}
      {step >= 3 && !result && (
        <Card className="border-0 bg-white shadow-[0_12px_32px_rgba(25,28,30,0.06)]">
          <CardHeader>
            <CardTitle className="text-base">
              Paso 3: Generar Documentos
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-[#434655] mb-3">
              Listo para generar documentos desde "{file?.name}" usando la plantilla "
              {templateName}".
            </p>
            <Button onClick={handleGenerate} disabled={bulkGenerate.isPending} className="bg-gradient-to-br from-[#004ac6] to-[#2563eb] text-white shadow-[0_4px_12px_rgba(0,74,198,0.3)]">
              {bulkGenerate.isPending ? "Generando..." : "Generar Documentos"}
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Step 4: Results */}
      {result && (
        <Card className="border-0 bg-white shadow-[0_12px_32px_rgba(25,28,30,0.06)]">
          <CardHeader>
            <CardTitle className="text-base">Resultados</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="rounded-lg bg-[#d1fae5] p-3">
              <p className="text-sm text-[#065f46]">
                Se generaron{" "}
                <strong>{result.document_count}</strong> documentos con éxito.
              </p>
            </div>
            {result.errors.length > 0 && (
              <div className="text-sm text-[#ba1a1a] rounded-lg bg-[#ffdad6] p-3">
                <p className="font-medium">Errores:</p>
                <ul className="list-disc pl-4">
                  {result.errors.map((e, i) => (
                    <li key={i}>
                      Fila {e.row}: {e.error}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            <BulkDownloadControls batchId={result.batch_id} isAdmin={isAdmin ?? false} />
          </CardContent>
        </Card>
      )}
    </div>
  );
}
