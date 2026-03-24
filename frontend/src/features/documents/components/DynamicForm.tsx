import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useGenerateDocument } from "../api/mutations";
import { apiClient } from "@/shared/lib/api-client";

interface DynamicFormProps {
  templateVersionId: string;
  variables: string[];
  templateName: string;
}

function buildSchema(variables: string[]) {
  const shape: Record<string, z.ZodString> = {};
  for (const v of variables) {
    shape[v] = z.string().min(1, `${v} es obligatorio`);
  }
  return z.object(shape);
}

export function DynamicForm({
  templateVersionId,
  variables,
  templateName: _,
}: DynamicFormProps) {
  const schema = buildSchema(variables);
  type FormData = z.infer<typeof schema>;

  const form = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: Object.fromEntries(variables.map((v) => [v, ""])),
  });

  const generateMutation = useGenerateDocument();
  const [documentId, setDocumentId] = useState<string | null>(null);
  const [fileName, setFileName] = useState<string>("");
  const [downloading, setDownloading] = useState(false);

  const onSubmit = async (data: FormData) => {
    try {
      const result = await generateMutation.mutateAsync({
        template_version_id: templateVersionId,
        variables: data,
      });
      setDocumentId(result.id);
      setFileName(result.file_name);
      toast.success("¡Documento generado con éxito!");
    } catch {
      toast.error("Error al generar el documento");
    }
  };

  const handleDownload = async () => {
    if (!documentId) return;
    setDownloading(true);
    try {
      const response = await apiClient.get(`/documents/${documentId}/download`, {
        responseType: "blob",
      });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", fileName);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch {
      toast.error("Error al descargar el documento");
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div className="space-y-6">
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
        {variables.map((variable) => (
          <div key={variable} className="space-y-2">
            <Label htmlFor={variable}>{variable}</Label>
            <Input
              id={variable}
              {...form.register(variable)}
              placeholder={`Ingrese ${variable}`}
            />
            {form.formState.errors[variable] && (
              <p className="text-sm text-destructive">
                {form.formState.errors[variable]?.message as string}
              </p>
            )}
          </div>
        ))}

        <Button type="submit" disabled={generateMutation.isPending}>
          {generateMutation.isPending ? "Generando..." : "Generar Documento"}
        </Button>
      </form>

      {documentId && (
        <div className="rounded-lg border p-4 bg-muted/50">
          <h3 className="font-semibold mb-2">Documento Listo</h3>
          <p className="text-sm text-muted-foreground mb-3">
            Su documento &quot;{fileName}&quot; ha sido generado.
          </p>
          <Button onClick={handleDownload} disabled={downloading}>
            {downloading ? "Descargando..." : "Descargar Documento"}
          </Button>
        </div>
      )}
    </div>
  );
}
