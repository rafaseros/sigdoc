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

interface VariableMeta {
  name: string;
  contexts: string[];
}

interface DynamicFormProps {
  templateVersionId: string;
  variables: string[];
  variablesMeta?: VariableMeta[];
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
  variablesMeta = [],
  templateName: _,
}: DynamicFormProps) {
  const schema = buildSchema(variables);
  type FormData = z.infer<typeof schema>;

  const form = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: Object.fromEntries(variables.map((v) => [v, ""])),
  });

  // Watch all values for live preview
  const watchedValues = form.watch();

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
        {variables.map((variable) => {
          const meta = variablesMeta.find((m) => m.name === variable);
          const currentValue = watchedValues[variable] || "";
          return (
            <div key={variable} className="space-y-2">
              <Label htmlFor={variable} className="font-semibold">
                {variable}
              </Label>
              {meta && meta.contexts.length > 0 && (
                <div className="space-y-1">
                  {meta.contexts.map((ctx, i) => (
                    <ContextPreview
                      key={i}
                      context={ctx}
                      variable={variable}
                      value={currentValue}
                    />
                  ))}
                </div>
              )}
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
          );
        })}

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

/**
 * Renders a paragraph context with the variable highlighted or replaced by the current value.
 * - No value: variable name shown highlighted in blue
 * - With value: replaced text shown highlighted in green
 */
function ContextPreview({
  context,
  variable,
  value,
}: {
  context: string;
  variable: string;
  value: string;
}) {
  // Match both {{ variable }} and {{variable}} patterns
  const pattern = new RegExp(
    `\\{\\{\\s*${variable.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\s*\\}\\}`,
    "g"
  );

  const parts: Array<{ text: string; isVariable: boolean }> = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = pattern.exec(context)) !== null) {
    if (match.index > lastIndex) {
      parts.push({ text: context.slice(lastIndex, match.index), isVariable: false });
    }
    parts.push({ text: match[0], isVariable: true });
    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < context.length) {
    parts.push({ text: context.slice(lastIndex), isVariable: false });
  }

  // If no matches found, show context as-is
  if (parts.length === 0) {
    parts.push({ text: context, isVariable: false });
  }

  return (
    <p className="text-xs text-muted-foreground bg-muted rounded px-2 py-1.5 font-mono leading-relaxed">
      {parts.map((part, i) =>
        part.isVariable ? (
          <span
            key={i}
            className={
              value
                ? "bg-green-200 dark:bg-green-900 text-green-900 dark:text-green-100 px-1 rounded font-sans font-medium"
                : "bg-blue-200 dark:bg-blue-900 text-blue-900 dark:text-blue-100 px-1 rounded"
            }
          >
            {value || part.text}
          </span>
        ) : (
          <span key={i}>{part.text}</span>
        )
      )}
    </p>
  );
}
