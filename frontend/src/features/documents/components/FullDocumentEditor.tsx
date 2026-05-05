/**
 * FullDocumentEditor.tsx
 *
 * Renders the complete .docx as a paginated document with three sections —
 * Encabezado / Contenido / Pie de página — and lets the user fill every
 * `{{ variable }}` placeholder inline through a popover. Unlike
 * InlineDocumentEditor, which only shows the paragraphs that contain a
 * specific variable, this view gives the full document context: surrounding
 * text, headers, and footers.
 *
 * Powered by GET /api/v1/templates/{tid}/versions/{vid}/structure.
 *
 * Auto-jump: every placeholder occurrence is tracked as a unique "instance"
 * (key derived from its position). When the user commits a value, the
 * editor advances to the next pending instance and opens its popover —
 * mirroring the InlineDocumentEditor behaviour.
 */

import { Fragment, useMemo, useState } from "react";
import { Popover } from "@base-ui/react/popover";
import { Select as BaseSelect } from "@base-ui/react/select";
import { Check, ChevronDown, FileText, Sparkles } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";

import { useGenerateDocument } from "../api/mutations";
import { DownloadButton } from "./DownloadButton";

import type {
  StructureNode,
  StructureSpan,
  TemplateStructure,
} from "@/features/templates/api/queries";
import type {
  VariableMeta,
  VariableType,
} from "@/features/templates/api/queries";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface FullDocumentEditorProps {
  templateVersionId: string;
  templateName: string;
  variablesMeta: VariableMeta[];
  structure: TemplateStructure;
}

interface GeneratedInfo {
  documentId: string;
  fileName: string;
}

// Each placeholder occurrence in the document gets a unique key so we can
// auto-jump from one pill to the next regardless of whether several pills
// reference the same variable name.
interface PlaceholderInstance {
  key: string;
  varName: string;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function humanLabel(name: string): string {
  return name.replace(/_/g, " ");
}

/** Build a stable instance key from its position in the structure. */
function instanceKey(
  section: "h" | "b" | "f",
  nodeIdx: number,
  spanIdx: number,
): string {
  return `${section}-${nodeIdx}-${spanIdx}`;
}

/** Flatten every placeholder occurrence in the document, preserving render order. */
function collectInstances(structure: TemplateStructure): PlaceholderInstance[] {
  const out: PlaceholderInstance[] = [];
  const sections: [Array<StructureNode>, "h" | "b" | "f"][] = [
    [structure.headers, "h"],
    [structure.body, "b"],
    [structure.footers, "f"],
  ];
  for (const [nodes, tag] of sections) {
    nodes.forEach((node, nodeIdx) => {
      node.spans.forEach((span, spanIdx) => {
        if (span.variable) {
          out.push({
            key: instanceKey(tag, nodeIdx, spanIdx),
            varName: span.variable,
          });
        }
      });
    });
  }
  return out;
}

// ---------------------------------------------------------------------------
// PlaceholderPill — controlled placeholder + popover
// ---------------------------------------------------------------------------

interface PlaceholderPillProps {
  varName: string;
  value: string;
  meta: VariableMeta | undefined;
  isEditing: boolean;
  onOpenChange: (open: boolean) => void;
  onCommit: (value: string) => void;
}

function PlaceholderPill({
  varName,
  value,
  meta,
  isEditing,
  onOpenChange,
  onCommit,
}: PlaceholderPillProps) {
  const [draft, setDraft] = useState(value);
  const filled = value.trim().length > 0;
  const label = humanLabel(varName);
  const type: VariableType = meta?.type ?? "text";
  const options = meta?.options ?? null;

  const handleOpenChange = (next: boolean) => {
    if (next) {
      setDraft(value);
    }
    onOpenChange(next);
  };

  const commit = (raw: string) => {
    onCommit(raw.trim());
  };

  return (
    <Popover.Root open={isEditing} onOpenChange={handleOpenChange}>
      <Popover.Trigger
        render={
          <button
            type="button"
            className={`var-chip ${filled ? "var-chip-active" : "var-chip-muted"} cursor-pointer hover:brightness-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]`}
            title={`Editar: ${label}`}
          />
        }
      >
        {filled ? value : `{{ ${varName} }}`}
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Positioner sideOffset={6}>
          <Popover.Popup className="z-50 w-72 rounded-xl bg-white p-4 shadow-[var(--shadow-lg)] ring-1 ring-[rgba(195,198,215,0.30)]">
            <div className="mb-2 flex items-start justify-between gap-2">
              <div>
                <Label className="text-[12.5px] font-semibold text-[var(--fg-1)]">
                  {label}
                </Label>
                <div className="font-mono text-[10.5px] text-[var(--fg-3)]">
                  {`{{ ${varName} }}`}
                </div>
              </div>
            </div>

            {meta?.help_text && (
              <p className="mb-2 text-[11.5px] italic text-[var(--fg-3)]">
                {meta.help_text}
              </p>
            )}

            {type === "select" && options && options.length > 0 ? (
              <SelectInput
                value={draft}
                options={options}
                onChange={(v) => setDraft(v)}
                onCommit={commit}
              />
            ) : (
              <Input
                autoFocus
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    commit(draft);
                  } else if (e.key === "Escape") {
                    onOpenChange(false);
                  }
                }}
                inputMode={
                  type === "integer"
                    ? "numeric"
                    : type === "decimal"
                      ? "decimal"
                      : "text"
                }
                placeholder={`Valor para ${label}`}
                className="h-9 text-sm"
              />
            )}

            <div className="mt-3 flex justify-end gap-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => onOpenChange(false)}
              >
                Cancelar
              </Button>
              <Button
                type="button"
                size="sm"
                onClick={() => commit(draft)}
                className="bg-gradient-to-br from-[#004ac6] to-[#2563eb] font-semibold text-white shadow-[var(--shadow-brand-sm)] hover:shadow-[var(--shadow-brand-md)]"
              >
                <Check className="size-3.5" />
                Confirmar
              </Button>
            </div>
          </Popover.Popup>
        </Popover.Positioner>
      </Popover.Portal>
    </Popover.Root>
  );
}

// Tiny wrapper around Base UI Select for the type=select popover content.
// Always controlled (value never `undefined`) — passing `undefined` only on
// the first render and a real value later flips the component from
// uncontrolled to controlled, which Base UI warns about.
function SelectInput({
  value,
  options,
  onChange,
  onCommit,
}: {
  value: string;
  options: string[];
  onChange: (v: string) => void;
  onCommit: (v: string) => void;
}) {
  return (
    <BaseSelect.Root
      value={value}
      onValueChange={(v) => {
        const next = (v as string) ?? "";
        onChange(next);
        // Defer the commit one frame: the BaseSelect needs to finish its
        // close + focus-restore cycle before the outer Popover unmounts
        // (auto-jump). Without this, focus has nowhere to land and the
        // browser scrolls back to the top of the page.
        requestAnimationFrame(() => onCommit(next));
      }}
    >
      <BaseSelect.Trigger className="flex h-9 w-full items-center justify-between rounded-lg border border-[rgba(195,198,215,0.50)] bg-white px-3 text-sm">
        <BaseSelect.Value placeholder="Seleccionar opción" />
        <ChevronDown className="size-3.5 text-[var(--fg-3)]" />
      </BaseSelect.Trigger>
      <BaseSelect.Portal>
        <BaseSelect.Positioner sideOffset={4}>
          <BaseSelect.Popup className="z-50 max-h-64 overflow-y-auto rounded-lg bg-white p-1 shadow-[var(--shadow-lg)] ring-1 ring-[rgba(195,198,215,0.30)]">
            {options.map((opt) => (
              <BaseSelect.Item
                key={opt}
                value={opt}
                className="flex cursor-pointer items-center justify-between rounded-md px-2.5 py-1.5 text-sm hover:bg-[var(--bg-page)] data-[highlighted]:bg-[var(--bg-accent)] data-[highlighted]:text-[var(--primary)]"
              >
                <BaseSelect.ItemText>{opt}</BaseSelect.ItemText>
              </BaseSelect.Item>
            ))}
          </BaseSelect.Popup>
        </BaseSelect.Positioner>
      </BaseSelect.Portal>
    </BaseSelect.Root>
  );
}

// ---------------------------------------------------------------------------
// DocumentNode — renders one paragraph or heading with its inline placeholders
// ---------------------------------------------------------------------------

interface DocumentNodeProps {
  node: StructureNode;
  section: "h" | "b" | "f";
  nodeIdx: number;
  values: Record<string, string>;
  metaByName: Record<string, VariableMeta>;
  editingKey: string | null;
  onOpenChange: (key: string, open: boolean) => void;
  onCommit: (key: string, varName: string, value: string) => void;
}

function DocumentNode({
  node,
  section,
  nodeIdx,
  values,
  metaByName,
  editingKey,
  onOpenChange,
  onCommit,
}: DocumentNodeProps) {
  const isHeading = node.kind === "heading";
  const headingClass =
    node.level === 1
      ? "text-xl font-bold tracking-tight text-[var(--fg-1)] mt-4 mb-2"
      : node.level === 2
        ? "text-lg font-bold tracking-tight text-[var(--fg-1)] mt-3 mb-2"
        : "text-base font-semibold tracking-tight text-[var(--fg-1)] mt-2 mb-1.5";

  const className = isHeading
    ? headingClass
    : "text-[14px] leading-[1.7] text-[var(--fg-1)] my-1.5";

  return (
    <p className={className}>
      {node.spans.map((span: StructureSpan, spanIdx) => {
        if (!span.variable) {
          return <Fragment key={spanIdx}>{span.text}</Fragment>;
        }
        const key = instanceKey(section, nodeIdx, spanIdx);
        return (
          <PlaceholderPill
            key={key}
            varName={span.variable}
            value={values[span.variable] ?? ""}
            meta={metaByName[span.variable]}
            isEditing={editingKey === key}
            onOpenChange={(open) => onOpenChange(key, open)}
            onCommit={(v) => onCommit(key, span.variable as string, v)}
          />
        );
      })}
    </p>
  );
}

// ---------------------------------------------------------------------------
// Main editor
// ---------------------------------------------------------------------------

export function FullDocumentEditor({
  templateVersionId,
  templateName,
  variablesMeta,
  structure,
}: FullDocumentEditorProps) {
  const instances = useMemo(() => collectInstances(structure), [structure]);
  const [values, setValues] = useState<Record<string, string>>({});
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [generated, setGenerated] = useState<GeneratedInfo | null>(null);

  const metaByName = useMemo(
    () => Object.fromEntries(variablesMeta.map((m) => [m.name, m])),
    [variablesMeta],
  );

  const generateMutation = useGenerateDocument();

  // Distinct variable names — used for the progress indicator (we want
  // "3 of 5 variables", not "3 of 17 placeholders").
  const distinctVarNames = useMemo(() => {
    const seen = new Set<string>();
    for (const inst of instances) seen.add(inst.varName);
    return Array.from(seen);
  }, [instances]);

  const filledCount = distinctVarNames.filter(
    (n) => (values[n] ?? "").trim().length > 0,
  ).length;
  const totalCount = distinctVarNames.length;
  const allFilled = filledCount === totalCount && totalCount > 0;
  const progress = totalCount === 0 ? 100 : (filledCount / totalCount) * 100;

  /** Find the next instance whose variable still has no value. */
  const nextPendingAfter = (currentKey: string): string | null => {
    const startIdx = instances.findIndex((i) => i.key === currentKey);
    if (startIdx === -1) return null;
    for (let i = startIdx + 1; i < instances.length; i++) {
      const inst = instances[i];
      if (!values[inst.varName] || values[inst.varName].trim() === "") {
        return inst.key;
      }
    }
    return null;
  };

  const handleOpenChange = (key: string, open: boolean) => {
    setEditingKey(open ? key : (current) =>
      // Only close if we're closing the currently-edited pill;
      // otherwise an unrelated trigger is just signalling its own state.
      current === key ? null : current,
    );
  };

  const handleCommit = (key: string, varName: string, value: string) => {
    // The popover swap (auto-jump) + Base UI focus restore can momentarily
    // push the page to scrollTop=0 — particularly when the source pill held
    // a Select whose close animation outraces the Popover unmount. Snapshot
    // the scroll position before mutating state and restore it next frame so
    // the user keeps their place in long documents.
    const scrollY = window.scrollY;
    setValues((prev) => ({ ...prev, [varName]: value }));
    const nextKey = nextPendingAfter(key);
    setEditingKey(nextKey);
    requestAnimationFrame(() => {
      if (Math.abs(window.scrollY - scrollY) > 4) {
        window.scrollTo({ top: scrollY, behavior: "instant" });
      }
    });
  };

  const handleGenerate = () => {
    if (!allFilled) {
      toast.error(
        `Faltan ${totalCount - filledCount} variable(s) por completar`,
      );
      return;
    }
    generateMutation.mutate(
      { template_version_id: templateVersionId, variables: values },
      {
        onSuccess: (doc) => {
          toast.success("Documento generado");
          setGenerated({
            documentId: doc.id,
            fileName: doc.docx_file_name,
          });
        },
        onError: () => {
          toast.error("Error al generar el documento");
        },
      },
    );
  };

  const hasHeaders = structure.headers.length > 0;
  const hasFooters = structure.footers.length > 0;

  return (
    <div className="flex flex-col gap-4">
      {/* Top progress bar */}
      <div className="rounded-xl bg-white p-4 shadow-[var(--shadow-sm)] ring-1 ring-[rgba(195,198,215,0.30)]">
        <div className="mb-2 flex items-center justify-between gap-3">
          <div>
            <div className="text-[13px] font-semibold text-[var(--fg-1)]">
              Progreso de la generación
            </div>
            <div className="text-[11.5px] text-[var(--fg-3)]">
              {filledCount} de {totalCount} variable
              {totalCount === 1 ? "" : "s"} completada
              {filledCount === 1 ? "" : "s"}
            </div>
          </div>
          {generated ? (
            <DownloadButton
              documentId={generated.documentId}
              baseFileName={generated.fileName}
              via="direct"
            />
          ) : (
            <Button
              size="sm"
              onClick={handleGenerate}
              disabled={!allFilled || generateMutation.isPending}
              className="bg-gradient-to-br from-[#004ac6] to-[#2563eb] font-semibold text-white shadow-[var(--shadow-brand-sm)] hover:shadow-[var(--shadow-brand-md)]"
            >
              <Sparkles className="size-3.5" />
              {generateMutation.isPending ? "Generando…" : "Generar documento"}
            </Button>
          )}
        </div>
        <Progress value={progress} className="h-1.5" />
      </div>

      {/* Document card */}
      <div className="overflow-hidden rounded-xl bg-white shadow-[var(--shadow-md)] ring-1 ring-[rgba(195,198,215,0.30)]">
        <div className="border-b border-[rgba(195,198,215,0.20)] bg-[var(--bg-page)] px-6 py-3">
          <div className="flex items-center gap-2 text-[12.5px] text-[var(--fg-3)]">
            <FileText className="size-4 text-[var(--primary)]" />
            <span className="font-medium text-[var(--fg-1)]">{templateName}</span>
          </div>
        </div>

        <div className="px-6 py-5">
          {hasHeaders && (
            <DocumentSection label="Encabezado">
              {structure.headers.map((node, i) => (
                <DocumentNode
                  key={`h-${i}`}
                  node={node}
                  section="h"
                  nodeIdx={i}
                  values={values}
                  metaByName={metaByName}
                  editingKey={editingKey}
                  onOpenChange={handleOpenChange}
                  onCommit={handleCommit}
                />
              ))}
            </DocumentSection>
          )}

          <DocumentSection label="Contenido" emphasis>
            {structure.body.length === 0 ? (
              <p className="text-[12.5px] italic text-[var(--fg-3)]">
                Este documento no tiene contenido en el cuerpo.
              </p>
            ) : (
              structure.body.map((node, i) => (
                <DocumentNode
                  key={`b-${i}`}
                  node={node}
                  section="b"
                  nodeIdx={i}
                  values={values}
                  metaByName={metaByName}
                  editingKey={editingKey}
                  onOpenChange={handleOpenChange}
                  onCommit={handleCommit}
                />
              ))
            )}
          </DocumentSection>

          {hasFooters && (
            <DocumentSection label="Pie de página">
              {structure.footers.map((node, i) => (
                <DocumentNode
                  key={`f-${i}`}
                  node={node}
                  section="f"
                  nodeIdx={i}
                  values={values}
                  metaByName={metaByName}
                  editingKey={editingKey}
                  onOpenChange={handleOpenChange}
                  onCommit={handleCommit}
                />
              ))}
            </DocumentSection>
          )}
        </div>
      </div>
    </div>
  );
}

function DocumentSection({
  label,
  emphasis = false,
  children,
}: {
  label: string;
  emphasis?: boolean;
  children: React.ReactNode;
}) {
  return (
    <section className={emphasis ? "mt-4 first:mt-0" : "mt-4 first:mt-0"}>
      <div className="sd-meta mb-2 inline-block rounded bg-[var(--bg-page)] px-2 py-0.5">
        {label}
      </div>
      <div
        className={
          emphasis
            ? ""
            : "rounded-lg bg-[var(--bg-page)] p-3 ring-1 ring-[rgba(195,198,215,0.20)]"
        }
      >
        {children}
      </div>
    </section>
  );
}
