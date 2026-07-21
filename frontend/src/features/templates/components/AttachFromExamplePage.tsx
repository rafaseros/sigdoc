/**
 * AttachFromExamplePage.tsx
 *
 * Full-page "attach a related document from an example" flow — the sibling
 * of CreateFromExamplePage for a template's CURRENT version:
 *   1. Upload a real, filled .docx — analyzed via POST
 *      /templates/analyze-example (stateless, reused as-is).
 *   2. Mark literal texts as variables over the shared read-only surface.
 *      The popover offers the template's EXISTING variables for REUSE:
 *      shared variables are the whole point of related documents, while a
 *      new name becomes an extra fill-in step at generation time — the UI
 *      flags both cases explicitly.
 *   3. POST /templates/{tid}/versions/{vid}/files/from-example rewrites the
 *      document and attaches it with the standard pipeline.
 *
 * Guard mirrors the "Agregar documento relacionado" button: owner or admin
 * (the backend re-validates role + ownership).
 */

import { useCallback, useMemo, useState } from "react";
import { useDropzone } from "react-dropzone";
import { useNavigate } from "@tanstack/react-router";
import { toast } from "sonner";
import {
  ArrowLeft,
  CircleAlert,
  Info,
  LoaderCircle,
  Paperclip,
  Upload,
  X,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

import { useTemplate } from "../api/queries";
import {
  useAnalyzeExample,
  useAttachVersionFileFromExample,
} from "../api/mutations";
import type { TemplateStructure } from "../api/queries";
import {
  buildExistingVariableOptions,
  countEffectiveOccurrences,
  newVariableNames,
  parseFromExampleError,
  type ExistingVariableOption,
  type FromExampleError,
  type VariableMapping,
} from "../lib/fromExample";
import { ExampleMarkingSurface, truncateText } from "./ExampleMarkingSurface";

const MAX_LABEL_LENGTH = 120;

// ---------------------------------------------------------------------------
// Page — guard + upload → mark steps
// ---------------------------------------------------------------------------

type Step = "select" | "analyzing" | "mark";

export function AttachFromExamplePage({ templateId }: { templateId: string }) {
  const { data: template, isLoading } = useTemplate(templateId);
  const navigate = useNavigate();

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

  if (isLoading) {
    return (
      <div className="flex flex-col items-center gap-3 rounded-xl bg-white py-14 shadow-[var(--shadow-sm)] ring-1 ring-[rgba(195,198,215,0.30)]">
        <LoaderCircle className="size-7 animate-spin text-[var(--primary)]" />
        <p className="text-sm font-medium text-[var(--fg-1)]">
          Cargando plantilla…
        </p>
      </div>
    );
  }

  const currentVersion = template?.versions.find(
    (v) => v.version === template.current_version,
  );

  if (!template || !currentVersion) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-12">
        <p className="text-[var(--fg-2)]">Plantilla no encontrada</p>
        <Button
          variant="outline"
          onClick={() => navigate({ to: "/templates" })}
        >
          <ArrowLeft />
          Volver a Plantillas
        </Button>
      </div>
    );
  }

  // UX mirror of the "Agregar documento relacionado" button's visibility —
  // the backend re-validates role and ownership.
  const isOwnerOrAdmin = template.is_owner || template.access_type === "admin";
  if (!isOwnerOrAdmin) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-12">
        <p className="text-[var(--fg-3)]">
          No tiene permisos para agregar documentos relacionados a esta
          plantilla.
        </p>
        <Button
          variant="outline"
          onClick={() =>
            navigate({ to: "/templates/$templateId", params: { templateId } })
          }
        >
          <ArrowLeft />
          Volver a la plantilla
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-start gap-3.5">
        <span className="inline-flex size-12 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-[#dbe1ff] to-[#b4c5ff] text-[var(--primary)]">
          <Paperclip className="size-5" />
        </span>
        <div className="min-w-0">
          <div className="sd-meta mb-1">
            Documento relacionado · {template.name}
          </div>
          <h1 className="m-0 text-[22px] font-bold tracking-tight text-[var(--fg-1)]">
            Adjuntar desde documento ejemplo
          </h1>
          <p className="mt-1 text-[13px] text-[var(--fg-3)]">
            Suba un documento real ya completado, marque los textos que se
            convertirán en variables y reutilice las variables existentes de
            la plantilla para compartir sus valores.
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
        <AttachMarkStep
          templateId={templateId}
          versionId={currentVersion.id}
          existingOptions={buildExistingVariableOptions(
            currentVersion.variables,
            currentVersion.files,
          )}
          file={file}
          structure={structure}
          onReset={handleReset}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Step 2 — mark variables with existing-variable reuse + label sidebar
// ---------------------------------------------------------------------------

function AttachMarkStep({
  templateId,
  versionId,
  existingOptions,
  file,
  structure,
  onReset,
}: {
  templateId: string;
  versionId: string;
  existingOptions: ExistingVariableOption[];
  file: File;
  structure: TemplateStructure;
  onReset: () => void;
}) {
  const navigate = useNavigate();
  const attachMutation = useAttachVersionFileFromExample();

  const [mappings, setMappings] = useState<VariableMapping[]>([]);
  const [label, setLabel] = useState("");
  const [submitError, setSubmitError] = useState<FromExampleError | null>(
    null,
  );

  const occurrenceByText = useMemo(
    () => countEffectiveOccurrences(structure, mappings),
    [mappings, structure],
  );
  const existingNames = useMemo(
    () => existingOptions.map((o) => o.name),
    [existingOptions],
  );
  const newNames = useMemo(
    () => newVariableNames(mappings, existingNames),
    [mappings, existingNames],
  );
  const existingNameSet = useMemo(
    () => new Set(existingNames),
    [existingNames],
  );

  function handleMappingsChange(next: VariableMapping[]) {
    setMappings(next);
    setSubmitError(null);
  }

  function handleRemoveMapping(text: string) {
    setMappings((prev) => prev.filter((m) => m.text !== text));
  }

  const trimmedLabel = label.trim();
  const labelTooLong = trimmedLabel.length > MAX_LABEL_LENGTH;
  const canSubmit =
    mappings.length > 0 &&
    trimmedLabel.length > 0 &&
    !labelTooLong &&
    !attachMutation.isPending;

  function handleSubmit() {
    if (!canSubmit) return;
    setSubmitError(null);
    attachMutation.mutate(
      {
        templateId,
        versionId,
        file,
        label: trimmedLabel,
        mappings,
      },
      {
        onSuccess: () => {
          toast.success("Documento relacionado agregado");
          navigate({
            to: "/templates/$templateId",
            params: { templateId },
            search: { tab: "versions" },
          });
        },
        onError: (error: unknown) => {
          const detail = (
            error as { response?: { data?: { detail?: unknown } } }
          )?.response?.data?.detail;
          const parsed = parseFromExampleError(
            detail,
            "Error al adjuntar el documento relacionado",
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
        existingVariables={existingOptions}
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
                const isExisting = existingNameSet.has(mapping.variable);
                return (
                  <li
                    key={mapping.text}
                    className="flex items-center justify-between gap-2 rounded-lg bg-[var(--bg-page)] px-2.5 py-2 ring-1 ring-[rgba(195,198,215,0.20)]"
                  >
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-1.5">
                        <span className="truncate font-mono text-xs font-medium text-[var(--primary)]">
                          {"{{ "}
                          {mapping.variable}
                          {" }}"}
                        </span>
                        {isExisting ? (
                          <span
                            className="shrink-0 rounded-full bg-[var(--bg-accent)] px-1.5 py-px text-[10.5px] font-semibold text-[var(--primary)]"
                            title="Reutiliza una variable existente de la plantilla"
                          >
                            Existente
                          </span>
                        ) : (
                          <span
                            className="shrink-0 rounded-full bg-[#fef3c7] px-1.5 py-px text-[10.5px] font-semibold text-[#78350f]"
                            title="Variable nueva — se pedirá al generar documentos"
                          >
                            Nueva
                          </span>
                        )}
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

          {/* New-variable summary — an extra fill-in step at generation */}
          {newNames.length > 0 && (
            <div className="flex items-start gap-2.5 rounded-[10px] bg-[#fef3c7] px-3.5 py-2.5 text-[12.5px] leading-[1.45] text-[#78350f]">
              <Info className="mt-px size-4 shrink-0" />
              <div className="flex-1">
                Este documento agrega {newNames.length}{" "}
                {newNames.length === 1
                  ? "variable nueva"
                  : "variables nuevas"}{" "}
                que se {newNames.length === 1 ? "pedirá" : "pedirán"} al
                generar documentos:{" "}
                <span className="font-mono">{newNames.join(", ")}</span>.
              </div>
            </div>
          )}

          <div className="border-t border-[rgba(195,198,215,0.20)] pt-4">
            <div className="grid gap-1.5">
              <Label
                htmlFor="attach-example-label"
                className="text-xs font-semibold uppercase tracking-[0.04em] text-[var(--fg-3)]"
              >
                Etiqueta <span className="text-[var(--destructive)]">*</span>
              </Label>
              <Input
                id="attach-example-label"
                value={label}
                onChange={(e) => {
                  setLabel(e.target.value);
                  setSubmitError(null);
                }}
                placeholder="Ej. Recibo de pago"
                required
              />
              {labelTooLong ? (
                <p className="m-0 text-[11px] text-[#93000a]">
                  La etiqueta no puede superar los {MAX_LABEL_LENGTH}{" "}
                  caracteres.
                </p>
              ) : (
                <p className="m-0 text-[11px] text-[var(--fg-3)]">
                  Identifica este documento en las pestañas del editor y en
                  el nombre del archivo generado.
                </p>
              )}
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
              {attachMutation.isPending ? (
                <>
                  <LoaderCircle className="mr-2 size-4 animate-spin" />
                  Adjuntando…
                </>
              ) : (
                <>
                  <Paperclip className="mr-2 size-4" />
                  Adjuntar documento
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
