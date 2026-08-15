import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { CircleCheck, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useGenerateDocument } from "../api/mutations";
import { DownloadButton } from "./DownloadButton";
import { GeneratedDocumentsList } from "./GeneratedDocumentsList";
import type { GeneratedDocumentInfo } from "./GeneratedDocumentsList";
import { InlineDocumentEditor } from "./InlineDocumentEditor";
import { VariableSourceChips } from "@/features/templates/components/VariableSourceChips";
import type { TemplateVersionFile } from "@/features/templates/api/queries";

interface VariableMeta {
  name: string;
  contexts: string[];
  /**
   * Optional author-written guidance for the variable. Shown as a small
   * description under the label in the "help" display mode (variant="fields").
   */
  help_text?: string | null;
  /**
   * Present (non-null) for server-computed variables (formula/function). Their
   * submitted values are discarded server-side, so the fallback form must
   * never require, render, or submit them. Structural marker — the concrete
   * config shape is owned by the API layer; only its presence matters here.
   */
  computed?: { kind: string } | null;
}

interface DynamicFormProps {
  templateVersionId: string;
  variables: string[];
  variablesMeta?: VariableMeta[];
  templateName: string;
  /**
   * - "auto" (default): preserve the historical behavior — switch to the
   *   InlineDocumentEditor for >= 4 variables, plain flat form otherwise.
   * - "flat": always render the plain flat form with each field's document
   *   context ("Guiado" mode), regardless of variable count.
   * - "fields": always render the plain flat form in "help" display — only the
   *   label + help text + input, no document context ("Rápido" mode).
   */
  variant?: "auto" | "flat" | "fields";
  /**
   * The version's related files. Threaded to DynamicFormFlat so each field can
   * surface which related documents also use that variable (see
   * VariableSourceChips). Defaults to `[]` — no provenance chips are shown when
   * the version has no related files. Ignored by the InlineDocumentEditor
   * branch, which exposes related documents through its own tabs.
   */
  files?: TemplateVersionFile[];
}

function buildSchema(variables: string[]) {
  const shape: Record<string, z.ZodString> = {};
  for (const v of variables) {
    shape[v] = z.string().min(1, `${v} es obligatorio`);
  }
  return z.object(shape);
}

/**
 * Routing wrapper:
 * - variant="flat"                        → DynamicFormFlat with document context ("Guiado")
 * - variant="fields"                      → DynamicFormFlat with help text only ("Rápido")
 * - variant="auto" & meta.length >= 4     → InlineDocumentEditor (document-like inline editing)
 * - variant="auto" & meta.length < 4      → DynamicFormFlat (original flat form, kept as fallback)
 *
 * Threshold of 4 balances UX: fewer variables don't benefit from the
 * document metaphor and are faster to fill with a plain form. "flat"/"fields"
 * opt out of that switch entirely for callers that want plain, fast data entry.
 */
export function DynamicForm({
  templateVersionId,
  variables,
  variablesMeta = [],
  templateName,
  variant = "auto",
  files = [],
}: DynamicFormProps) {
  const effectiveMeta =
    variablesMeta.length > 0
      ? variablesMeta
      : variables.map((name) => ({ name, contexts: [] }));

  if (variant === "auto" && effectiveMeta.length >= 4) {
    return (
      <InlineDocumentEditor
        templateVersionId={templateVersionId}
        variablesMeta={effectiveMeta}
        templateName={templateName}
      />
    );
  }

  return (
    <DynamicFormFlat
      templateVersionId={templateVersionId}
      variables={variables}
      variablesMeta={variablesMeta}
      display={variant === "fields" ? "help" : "context"}
      files={files}
    />
  );
}

/**
 * Original flat form — used as the < 4-variable fallback for variant="auto"
 * and as the always-on form for variant="flat"/"fields".
 *
 * `display` selects how much document context each field carries:
 * - "context" (default): show the ContextPreview(s) — where the value lands in
 *   the document — and no help text. Keeps backward compatibility.
 * - "help": show only the variable's help text (when present) as a small
 *   description under the label — no document context at all.
 */
function DynamicFormFlat({
  templateVersionId,
  variables,
  variablesMeta = [],
  display = "context",
  files = [],
}: Omit<DynamicFormProps, "templateName" | "variant"> & {
  display?: "context" | "help";
}) {
  // Computed variables are resolved server-side and their submitted values are
  // discarded — exclude them from the required schema, the rendered fields,
  // and the payload so the user is never forced to invent a value for an
  // "automatic" variable before Generate enables.
  const computedNames = new Set(
    variablesMeta.filter((m) => m.computed).map((m) => m.name),
  );
  const editableVariables = variables.filter((v) => !computedNames.has(v));

  const schema = buildSchema(editableVariables);
  type FormData = z.infer<typeof schema>;

  const form = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: Object.fromEntries(editableVariables.map((v) => [v, ""])),
  });

  // Watch all values for live preview
  const watchedValues = form.watch();

  const generateMutation = useGenerateDocument();
  const [generatedDocs, setGeneratedDocs] = useState<GeneratedDocumentInfo[]>(
    [],
  );

  const onSubmit = async (data: FormData) => {
    try {
      const result = await generateMutation.mutateAsync({
        template_version_id: templateVersionId,
        variables: data,
      });
      const docs = result.documents.map((d) => ({
        documentId: d.id,
        fileName: d.docx_file_name,
      }));
      setGeneratedDocs(docs);
      toast.success(
        docs.length === 1
          ? "Documento generado"
          : `${docs.length} documentos generados`,
      );
    } catch {
      toast.error("Error al generar el documento");
    }
  };

  return (
    <div className="space-y-5">
      <form
        onSubmit={form.handleSubmit(onSubmit)}
        className="rounded-xl bg-white p-5 shadow-[var(--shadow-sm)] ring-1 ring-[rgba(195,198,215,0.30)] space-y-4"
      >
        <div>
          <h3 className="m-0 text-base font-bold tracking-tight text-[var(--fg-1)]">
            Complete las variables
          </h3>
          <p className="mt-0.5 text-[12.5px] text-[var(--fg-3)]">
            Cada campo se reemplazará en el documento generado.
          </p>
        </div>

        {editableVariables.map((variable) => {
          const meta = variablesMeta.find((m) => m.name === variable);
          const currentValue = watchedValues[variable] || "";
          const helpText = meta?.help_text?.trim();
          return (
            <div key={variable} className="space-y-1.5">
              <Label
                htmlFor={variable}
                className="text-[12.5px] font-semibold text-[var(--fg-2)]"
              >
                <span className="font-mono text-[var(--primary)]">
                  {variable}
                </span>
              </Label>
              {/* Provenance: which related documents also use this variable.
                  Shown in both display modes, right under the label so it reads
                  as belonging to this field. Renders nothing when no related
                  file uses the variable. */}
              <VariableSourceChips variableName={variable} files={files} />
              {display === "context" && meta && meta.contexts.length > 0 && (
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
              {display === "help" && helpText && (
                <p className="text-[12px] leading-relaxed text-[var(--fg-3)]">
                  {helpText}
                </p>
              )}
              <Input
                id={variable}
                {...form.register(variable)}
                placeholder={`Ingrese ${variable}`}
                className="bg-[var(--bg-muted)] border-transparent focus:border-[#2563eb] focus:ring-[#2563eb]/20 transition-all"
              />
              {form.formState.errors[variable] && (
                <p className="text-[12.5px] text-[var(--destructive)]">
                  {form.formState.errors[variable]?.message as string}
                </p>
              )}
            </div>
          );
        })}

        <div className="flex justify-end pt-2">
          <Button
            type="submit"
            disabled={generateMutation.isPending}
            className="bg-gradient-to-br from-[#004ac6] to-[#2563eb] font-semibold text-white shadow-[var(--shadow-brand-sm)] hover:shadow-[var(--shadow-brand-md)] transition-all"
          >
            <Sparkles className="size-4" />
            {generateMutation.isPending ? "Generando..." : "Generar documento"}
          </Button>
        </div>
      </form>

      {generatedDocs.length > 0 && (
        <div className="rounded-xl bg-[#d1fae5] p-5 shadow-[0_4px_16px_rgba(5,150,105,0.10)]">
          <div className="mb-2 flex items-center gap-2">
            <CircleCheck className="size-4 text-[#059669]" />
            <h3 className="m-0 text-[14px] font-bold text-[#065f46]">
              {generatedDocs.length === 1
                ? "Documento listo"
                : "Documentos listos"}
            </h3>
          </div>
          {generatedDocs.length === 1 ? (
            <>
              <p className="mb-3 text-[13px] text-[#047857]">
                Su documento &quot;{generatedDocs[0].fileName}&quot; ha sido
                generado correctamente.
              </p>
              <DownloadButton
                documentId={generatedDocs[0].documentId}
                baseFileName={generatedDocs[0].fileName}
                via="direct"
              />
            </>
          ) : (
            <>
              <p className="mb-3 text-[13px] text-[#047857]">
                Se generaron {generatedDocs.length} documentos con los mismos
                datos.
              </p>
              <GeneratedDocumentsList documents={generatedDocs} />
            </>
          )}
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
    <p className="break-words text-xs text-[var(--fg-2)] bg-[var(--bg-muted)] rounded-lg px-3 py-2 font-mono leading-relaxed">
      {parts.map((part, i) =>
        part.isVariable ? (
          <span
            key={i}
            className={
              value
                ? "bg-[#d1fae5] text-[#065f46] px-1 rounded font-sans font-medium"
                : "bg-[var(--bg-accent)] text-[var(--primary)] px-1 rounded"
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
