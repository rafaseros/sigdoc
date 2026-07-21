/**
 * CreateFromExamplePage.tsx
 *
 * Full-page "create template from example" flow:
 *   1. Upload a real, filled .docx (no placeholders required) — analyzed via
 *      POST /templates/analyze-example.
 *   2. The document renders read-only; the user selects literal text with
 *      the mouse, names a variable for it, and every exact occurrence gets
 *      highlighted. Mappings accumulate in a sidebar panel.
 *   3. POST /templates/from-example creates the template (v1) with the
 *      mappings as {{ placeholders }}.
 *
 * The read-only renderer + selection popover live in ExampleMarkingSurface
 * (shared with the attach-related-file-from-example flow).
 */

import { useMemo, useState, useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { useNavigate } from "@tanstack/react-router";
import { toast } from "sonner";
import {
  CircleAlert,
  LoaderCircle,
  ScanText,
  Upload,
  X,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

import {
  useAnalyzeExample,
  useCreateTemplateFromExample,
} from "../api/mutations";
import type { TemplateStructure } from "../api/queries";
import {
  countEffectiveOccurrences,
  parseFromExampleError,
  type FromExampleError,
  type VariableMapping,
} from "../lib/fromExample";
import { ExampleMarkingSurface, truncateText } from "./ExampleMarkingSurface";

// ---------------------------------------------------------------------------
// Page — orchestrates the upload → mark steps
// ---------------------------------------------------------------------------

type Step = "select" | "analyzing" | "mark";

export function CreateFromExamplePage() {
  const [step, setStep] = useState<Step>("select");
  const [file, setFile] = useState<File | null>(null);
  const [structure, setStructure] = useState<TemplateStructure | null>(null);
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);

  const analyzeMutation = useAnalyzeExample();

  const onDrop = useCallback(
    async (acceptedFiles: File[]) => {
      if (acceptedFiles.length === 0) return;
      const selected = acceptedFiles[0];
      setFile(selected);
      setAnalyzeError(null);
      setStep("analyzing");
      try {
        const result = await analyzeMutation.mutateAsync(selected);
        setStructure(result);
        setStep("mark");
      } catch (error: unknown) {
        const detail = (
          error as { response?: { data?: { detail?: unknown } } }
        )?.response?.data?.detail;
        setAnalyzeError(
          typeof detail === "string" && detail
            ? detail
            : "Error al analizar el documento de ejemplo",
        );
        setFile(null);
        setStep("select");
      }
    },
    [analyzeMutation],
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        [".docx"],
    },
    maxFiles: 1,
    disabled: step === "analyzing",
  });

  function handleReset() {
    setFile(null);
    setStructure(null);
    setAnalyzeError(null);
    setStep("select");
  }

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-start gap-3.5">
        <span className="inline-flex size-12 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-[#dbe1ff] to-[#b4c5ff] text-[var(--primary)]">
          <ScanText className="size-5" />
        </span>
        <div className="min-w-0">
          <div className="sd-meta mb-1">Nueva plantilla</div>
          <h1 className="m-0 text-[22px] font-bold tracking-tight text-[var(--fg-1)]">
            Crear plantilla desde ejemplo
          </h1>
          <p className="mt-1 text-[13px] text-[var(--fg-3)]">
            Suba un documento real ya completado y marque los textos que se
            convertirán en variables.
          </p>
        </div>
      </div>

      {/* Step: select */}
      {step === "select" && (
        <div className="rounded-xl bg-white p-5 shadow-[var(--shadow-sm)] ring-1 ring-[rgba(195,198,215,0.30)]">
          {analyzeError && (
            <div className="mb-4 flex items-start gap-2.5 rounded-[10px] bg-[#ffdad6] px-3.5 py-3 text-[13px] leading-[1.45] text-[#93000a]">
              <CircleAlert className="mt-px size-4 shrink-0" />
              <div className="flex-1">{analyzeError}</div>
            </div>
          )}
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
                : "Arrastre y suelte un documento .docx de ejemplo"}
            </div>
            <div className="text-xs text-[var(--fg-3)]">
              o haga clic para buscar · un documento real ya completado, sin
              marcadores
            </div>
          </div>
        </div>
      )}

      {/* Step: analyzing */}
      {step === "analyzing" && (
        <div className="flex flex-col items-center gap-3 rounded-xl bg-white py-14 shadow-[var(--shadow-sm)] ring-1 ring-[rgba(195,198,215,0.30)]">
          <LoaderCircle className="size-7 animate-spin text-[var(--primary)]" />
          <p className="text-sm font-medium text-[var(--fg-1)]">
            Analizando {file?.name ?? "documento"}…
          </p>
        </div>
      )}

      {/* Step: mark */}
      {step === "mark" && file && structure && (
        <MarkVariablesStep
          file={file}
          structure={structure}
          onReset={handleReset}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Step 2 — mark variables over the read-only rendered document
// ---------------------------------------------------------------------------

export function MarkVariablesStep({
  file,
  structure,
  onReset,
}: {
  file: File;
  structure: TemplateStructure;
  onReset: () => void;
}) {
  const navigate = useNavigate();
  const createMutation = useCreateTemplateFromExample();

  const [mappings, setMappings] = useState<VariableMapping[]>([]);
  const [name, setName] = useState(() => file.name.replace(/\.docx$/, ""));
  const [description, setDescription] = useState("");
  const [submitError, setSubmitError] = useState<FromExampleError | null>(
    null,
  );

  // Effective (surviving) occurrences per mapping — what the backend will
  // actually replace once longer mappings consume contained texts.
  const occurrenceByText = useMemo(
    () => countEffectiveOccurrences(structure, mappings),
    [mappings, structure],
  );

  function handleMappingsChange(next: VariableMapping[]) {
    setMappings(next);
    setSubmitError(null);
  }

  function handleRemoveMapping(text: string) {
    setMappings((prev) => prev.filter((m) => m.text !== text));
  }

  const canSubmit =
    mappings.length > 0 && name.trim().length > 0 && !createMutation.isPending;

  function handleSubmit() {
    if (!canSubmit) return;
    setSubmitError(null);
    createMutation.mutate(
      {
        file,
        name: name.trim(),
        description: description.trim() || undefined,
        mappings,
      },
      {
        onSuccess: (created) => {
          toast.success(`Plantilla «${created.name}» creada con éxito`);
          navigate({
            to: "/templates/$templateId",
            params: { templateId: created.id },
          });
        },
        onError: (error: unknown) => {
          const detail = (
            error as { response?: { data?: { detail?: unknown } } }
          )?.response?.data?.detail;
          const parsed = parseFromExampleError(
            detail,
            "Error al crear la plantilla",
          );
          setSubmitError(parsed);
          toast.error(parsed.message);
        },
      },
    );
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
      <ExampleMarkingSurface
        file={file}
        structure={structure}
        mappings={mappings}
        onMappingsChange={handleMappingsChange}
      />

      {/* Sidebar panel */}
      <aside className="self-start lg:sticky lg:top-20">
        <div className="flex flex-col gap-4 rounded-xl bg-white p-4 shadow-[var(--shadow-sm)] ring-1 ring-[rgba(195,198,215,0.30)]">
          <div>
            <div className="text-[13px] font-semibold text-[var(--fg-1)]">
              Variables marcadas
            </div>
            <div className="text-[11.5px] text-[var(--fg-3)]">
              {mappings.length}{" "}
              {mappings.length === 1 ? "variable" : "variables"}
            </div>
          </div>

          {mappings.length === 0 ? (
            <p className="text-[12.5px] text-[var(--fg-3)]">
              Aún no hay variables. Seleccione texto en el documento para
              crear la primera.
            </p>
          ) : (
            <ul className="flex max-h-64 flex-col gap-1.5 overflow-y-auto">
              {mappings.map((mapping) => {
                const count = occurrenceByText.get(mapping.text) ?? 0;
                return (
                  <li
                    key={mapping.text}
                    className="flex items-center justify-between gap-2 rounded-lg bg-[var(--bg-page)] px-2.5 py-2 ring-1 ring-[rgba(195,198,215,0.20)]"
                  >
                    <div className="min-w-0 flex-1">
                      <div className="truncate font-mono text-xs font-medium text-[var(--primary)]">
                        {"{{ "}
                        {mapping.variable}
                        {" }}"}
                      </div>
                      <div
                        className="truncate text-[11.5px] text-[var(--fg-3)]"
                        title={mapping.text}
                      >
                        «{truncateText(mapping.text, 40)}»
                      </div>
                    </div>
                    <Badge
                      variant="outline"
                      className="shrink-0 rounded-full border-[rgba(195,198,215,0.40)] px-1.5 text-[10.5px] text-[var(--fg-3)]"
                      title={`${count} ${count === 1 ? "aparición" : "apariciones"} en el documento`}
                    >
                      ×{count}
                    </Badge>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon-sm"
                      aria-label={`Quitar variable ${mapping.variable}`}
                      onClick={() => handleRemoveMapping(mapping.text)}
                      className="shrink-0 text-[var(--fg-2)] hover:bg-[#ffdad6]/50 hover:text-[var(--destructive)]"
                    >
                      <X className="size-4" />
                    </Button>
                  </li>
                );
              })}
            </ul>
          )}

          <div className="border-t border-[rgba(195,198,215,0.20)] pt-4">
            <div className="flex flex-col gap-4">
              <div className="grid gap-1.5">
                <Label
                  htmlFor="from-example-name"
                  className="text-xs font-semibold uppercase tracking-[0.04em] text-[var(--fg-3)]"
                >
                  Nombre <span className="text-[var(--destructive)]">*</span>
                </Label>
                <Input
                  id="from-example-name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Ej. Contrato de Trabajo"
                  required
                />
              </div>
              <div className="grid gap-1.5">
                <Label
                  htmlFor="from-example-description"
                  className="text-xs font-semibold uppercase tracking-[0.04em] text-[var(--fg-3)]"
                >
                  Descripción (opcional)
                </Label>
                <Textarea
                  id="from-example-description"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="¿Para qué se usa esta plantilla?"
                  rows={3}
                />
              </div>
            </div>
          </div>

          {submitError && (
            <div className="flex items-start gap-2.5 rounded-[10px] bg-[#ffdad6] px-3.5 py-3 text-[13px] leading-[1.45] text-[#93000a]">
              <CircleAlert className="mt-px size-4 shrink-0" />
              <div className="flex-1">
                <p className="m-0">{submitError.message}</p>
                {submitError.items.length > 0 && (
                  <ul className="mt-1.5 list-disc space-y-0.5 pl-4">
                    {submitError.items.map((item, i) => (
                      <li key={i} className="font-mono text-xs">
                        {item}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          )}

          <div className="flex flex-col gap-2">
            <Button
              type="button"
              onClick={handleSubmit}
              disabled={!canSubmit}
              className="bg-gradient-to-br from-[#004ac6] to-[#2563eb] font-semibold text-white shadow-[var(--shadow-brand-sm)] hover:shadow-[var(--shadow-brand-md)] disabled:opacity-60"
            >
              {createMutation.isPending ? (
                <>
                  <LoaderCircle className="mr-2 size-4 animate-spin" />
                  Creando…
                </>
              ) : (
                <>
                  <ScanText className="mr-2 size-4" />
                  Crear Plantilla
                </>
              )}
            </Button>
            <Button type="button" variant="outline" onClick={onReset}>
              Elegir otro archivo
            </Button>
          </div>
        </div>
      </aside>
    </div>
  );
}
