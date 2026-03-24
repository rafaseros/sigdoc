import { useState } from "react";
import { useDropzone } from "react-dropzone";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useDownloadExcelTemplate, useBulkGenerate } from "../api/mutations";
import { apiClient } from "@/shared/lib/api-client";

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
  const [downloading, setDownloading] = useState(false);

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

  const handleDownloadZip = async () => {
    if (!result) return;
    setDownloading(true);
    try {
      const response = await apiClient.get(result.download_url, {
        responseType: "blob",
      });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", `bulk_${result.batch_id}.zip`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch {
      toast.error("Error al descargar el ZIP");
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Step indicators */}
      <div className="flex gap-2">
        {[1, 2, 3, 4].map((s) => (
          <div
            key={s}
            className={`h-2 flex-1 rounded ${
              s <= step ? "bg-primary" : "bg-muted"
            }`}
          />
        ))}
      </div>

      {/* Step 1: Download Excel */}
      {step >= 1 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">
              Paso 1: Descargar Plantilla Excel
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground mb-3">
              Descargue el archivo Excel con {variableCount} columnas de variables.
              Complete cada fila con datos (máximo 10 filas).
            </p>
            <Button
              onClick={handleDownloadExcel}
              disabled={downloadExcel.isPending}
              variant={step > 1 ? "outline" : "default"}
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
        <Card>
          <CardHeader>
            <CardTitle className="text-base">
              Paso 2: Subir Excel Completado
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div
              {...getRootProps()}
              className={`border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors ${
                isDragActive
                  ? "border-primary bg-primary/5"
                  : "border-muted-foreground/25"
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
                <p className="text-sm text-muted-foreground">
                  Arrastre y suelte su archivo .xlsx completado, o haga clic para buscar
                </p>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Step 3: Confirm & Generate */}
      {step >= 3 && !result && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">
              Paso 3: Generar Documentos
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground mb-3">
              Listo para generar documentos desde "{file?.name}" usando la plantilla "
              {templateName}".
            </p>
            <Button onClick={handleGenerate} disabled={bulkGenerate.isPending}>
              {bulkGenerate.isPending ? "Generando..." : "Generar Documentos"}
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Step 4: Results */}
      {result && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Resultados</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm">
              Se generaron{" "}
              <strong>{result.document_count}</strong> documentos con éxito.
            </p>
            {result.errors.length > 0 && (
              <div className="text-sm text-destructive">
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
            <Button onClick={handleDownloadZip} disabled={downloading}>
              {downloading ? "Descargando..." : "Descargar ZIP"}
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
