/**
 * InlineDocumentEditor.tsx
 *
 * Inline document editor for the SigDoc generation flow.
 * Each {{ variable }} in the template is rendered as a clickable pill;
 * clicking opens a small popover with an input — no separate form needed.
 *
 * Activated when variablesMeta.length >= 4.
 * For < 4 variables the caller falls back to DynamicFormFlat.
 */

import { Fragment, useState, useRef, useCallback, useEffect, useMemo } from "react";
import { Popover } from "@base-ui/react/popover";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { DownloadButton } from "./DownloadButton";
import { useGenerateDocument } from "../api/mutations";
import {
  assembleDocument,
  type VariableMeta,
  type DocumentParagraph,
  type DocumentSegment,
} from "@/lib/assemble-document";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface InlineDocumentEditorProps {
  templateVersionId: string;
  variablesMeta: VariableMeta[];
  templateName: string;
}

/**
 * Unique key that identifies a single pill occurrence in the document.
 * Format: `${paragraphId}::${segmentIndex}`.
 * Two pills with the same varName but different positions will have different instanceKeys.
 */
type InstanceKey = string;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Convert snake_case/camelCase to "human label": nombre_empresa → nombre de empresa */
function humanLabel(name: string): string {
  return name.replace(/_/g, " ");
}

/**
 * Heuristic: use a Textarea for variables whose name suggests multi-line content.
 * Single-line Input is the default.
 */
function isMultiline(name: string): boolean {
  return /literal|descripcion|descripci[oó]n|direccion|direcci[oó]n|detalle|nota/i.test(name);
}

// ---------------------------------------------------------------------------
// PlaceholderWidget
// ---------------------------------------------------------------------------

interface PlaceholderWidgetProps {
  varName: string;
  instanceKey: InstanceKey;
  value: string;
  isEditing: boolean;
  onOpen: () => void;
  onClose: () => void;
  onCommit: (val: string) => void;
  /** Ref callback so the parent can track DOM nodes for keyboard navigation */
  pillRef?: (el: HTMLButtonElement | null) => void;
}

function PlaceholderWidget({
  varName,
  instanceKey,
  value,
  isEditing,
  onOpen,
  onClose,
  onCommit,
  pillRef,
}: PlaceholderWidgetProps) {
  const [draft, setDraft] = useState(value);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  // Stable ref for the pill button — used as anchor for the positioner
  const pillButtonRef = useRef<HTMLButtonElement | null>(null);
  const multiline = isMultiline(varName);
  const label = humanLabel(varName);
  const isFilled = value.trim().length > 0;

  // Sync draft when popover opens + auto-focus input
  useEffect(() => {
    if (isEditing) {
      setDraft(value);
      requestAnimationFrame(() => {
        inputRef.current?.focus();
        textareaRef.current?.focus();
      });
    }
  }, [isEditing, value]);

  function handleCommit() {
    const trimmed = draft.trim();
    if (trimmed) {
      onCommit(trimmed);
    }
    onClose();
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !multiline) {
      e.preventDefault();
      handleCommit();
    }
    if (e.key === "Escape") {
      onClose();
    }
  }

  // instanceKey is used by the parent for identity — not needed in JSX directly,
  // but we keep it in props so TypeScript enforces the caller passes it.
  void instanceKey;

  return (
    <>
      {/* Pill button — the anchor for the popover positioner */}
      <button
        ref={(el) => {
          pillButtonRef.current = el;
          pillRef?.(el);
        }}
        type="button"
        onClick={onOpen}
        className={cn(
          "inline-flex items-center gap-1 px-2 py-0.5 rounded text-sm font-medium transition-all cursor-pointer select-none",
          "align-baseline mx-0.5 whitespace-normal",
          isFilled
            ? "bg-green-50 text-green-800 border border-solid border-green-300 hover:bg-green-100"
            : "bg-blue-50 text-blue-700 border border-dashed border-blue-300 hover:bg-blue-100",
          isEditing && "ring-2 ring-blue-400 ring-offset-0",
        )}
      >
        {!isFilled && (
          <span className="text-blue-400 font-bold text-xs leading-none">+</span>
        )}
        <span>{isFilled ? value : label}</span>
      </button>

      {/* Controlled popover anchored to the pill */}
      <Popover.Root
        open={isEditing}
        onOpenChange={(open) => {
          if (!open) onClose();
        }}
      >
        {/*
          Popover.Trigger is required by Popover.Root for positioning context.
          We hide it visually and position it over the pill using absolute CSS so
          the positioner anchors correctly, then the actual visible pill is above.
        */}
        <Popover.Trigger
          aria-hidden="true"
          tabIndex={-1}
          className="sr-only"
        />

        <Popover.Portal>
          <Popover.Positioner
            anchor={pillButtonRef}
            side="bottom"
            align="start"
            sideOffset={6}
          >
            <Popover.Popup
              className={cn(
                "z-50 w-72 rounded-xl border border-border bg-white p-4",
                "shadow-[0_8px_24px_rgba(25,28,30,0.12)]",
                "outline-none",
              )}
            >
              <Label
                htmlFor={`popover-input-${varName}`}
                className="block text-xs font-semibold text-muted-foreground mb-2 capitalize"
              >
                {label}
              </Label>

              {multiline ? (
                <Textarea
                  id={`popover-input-${varName}`}
                  ref={textareaRef}
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder={`Ingrese ${label}`}
                  className="bg-[#e6e8ea] border-transparent focus:border-[#2563eb] focus:ring-[#2563eb]/20 text-sm resize-none min-h-20"
                />
              ) : (
                <div className="relative">
                  <Input
                    id={`popover-input-${varName}`}
                    ref={inputRef}
                    value={draft}
                    onChange={(e) => setDraft(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder={`Ingrese ${label}`}
                    className="bg-[#e6e8ea] border-transparent focus:border-[#2563eb] focus:ring-[#2563eb]/20 pr-10 text-sm"
                  />
                  {/* ↵ Enter hint */}
                  <span className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 text-[10px] text-muted-foreground/60 font-mono">
                    ↵
                  </span>
                </div>
              )}

              <div className="mt-3 flex justify-end gap-2">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={onClose}
                  className="text-xs"
                >
                  Cancelar
                </Button>
                <Button
                  type="button"
                  size="sm"
                  onClick={handleCommit}
                  className="text-xs bg-gradient-to-br from-[#004ac6] to-[#2563eb] text-white shadow-[0_2px_8px_rgba(0,74,198,0.3)]"
                >
                  Confirmar
                </Button>
              </div>
            </Popover.Popup>
          </Popover.Positioner>
        </Popover.Portal>
      </Popover.Root>
    </>
  );
}

// ---------------------------------------------------------------------------
// Paragraph renderer
// ---------------------------------------------------------------------------

interface ParagraphRendererProps {
  paragraph: DocumentParagraph;
  values: Record<string, string>;
  editingInstance: InstanceKey | null;
  onSegmentOpen: (instanceKey: InstanceKey, varName: string) => void;
  onSegmentClose: () => void;
  onCommit: (varName: string, val: string) => void;
  registerPill: (instanceKey: InstanceKey, el: HTMLButtonElement | null) => void;
}

function ParagraphRenderer({
  paragraph,
  values,
  editingInstance,
  onSegmentOpen,
  onSegmentClose,
  onCommit,
  registerPill,
}: ParagraphRendererProps) {
  return (
    <p className="text-[15px] leading-8 text-[#191c1e] font-serif">
      {paragraph.segments.map((seg: DocumentSegment, i: number) => {
        if (seg.type === "text") {
          return <span key={i}>{seg.content}</span>;
        }
        const varName = seg.content;
        const instanceKey: InstanceKey = `${paragraph.id}::${i}`;
        return (
          <PlaceholderWidget
            key={instanceKey}
            varName={varName}
            instanceKey={instanceKey}
            value={values[varName] ?? ""}
            isEditing={editingInstance === instanceKey}
            onOpen={() => onSegmentOpen(instanceKey, varName)}
            onClose={onSegmentClose}
            onCommit={(val) => onCommit(varName, val)}
            pillRef={(el) => registerPill(instanceKey, el)}
          />
        );
      })}
    </p>
  );
}

// ---------------------------------------------------------------------------
// InlineDocumentEditor (main export)
// ---------------------------------------------------------------------------

export function InlineDocumentEditor({
  templateVersionId,
  variablesMeta,
  templateName,
}: InlineDocumentEditorProps) {
  const [values, setValues] = useState<Record<string, string>>({});
  const [editingInstance, setEditingInstance] = useState<InstanceKey | null>(null);
  const [documentId, setDocumentId] = useState<string | null>(null);
  const [fileName, setFileName] = useState<string>("");

  // Map: instanceKey → pill button DOM node (for keyboard nav + "Próximo campo")
  const pillRefs = useRef<Map<InstanceKey, HTMLButtonElement>>(new Map());

  const generateMutation = useGenerateDocument();

  // Assemble the document once — variablesMeta is stable after the query resolves
  const paragraphs = useMemo(() => assembleDocument(variablesMeta), [variablesMeta]);

  // Ordered list of unique variable names across the document (for progress counting)
  const allVarNames = useMemo(() => {
    const result: string[] = [];
    const seen = new Set<string>();
    for (const p of paragraphs) {
      for (const v of p.variableNames) {
        if (!seen.has(v)) {
          seen.add(v);
          result.push(v);
        }
      }
    }
    return result;
  }, [paragraphs]);

  /**
   * Flattened ordered list of all placeholder instances across the document.
   * Each entry carries its instanceKey and varName so "Próximo campo" can walk
   * by occurrence rather than by variable name.
   */
  const allInstances = useMemo(() => {
    const result: Array<{ instanceKey: InstanceKey; varName: string }> = [];
    for (const p of paragraphs) {
      p.segments.forEach((seg, i) => {
        if (seg.type !== "text") {
          result.push({ instanceKey: `${p.id}::${i}`, varName: seg.content });
        }
      });
    }
    return result;
  }, [paragraphs]);

  const filledCount = allVarNames.filter(
    (v) => (values[v] ?? "").trim().length > 0
  ).length;
  const totalCount = allVarNames.length;
  const allFilled = filledCount === totalCount && totalCount > 0;

  // ---------------------------------------------------------------------------
  // Handlers
  // ---------------------------------------------------------------------------

  const handleCommit = useCallback((varName: string, val: string) => {
    // Detect whether this commit fills a previously-empty field.
    // If so, auto-jump to the next unfilled instance — keeps the user in flow
    // without needing a "next field" button. If the user is editing an
    // already-filled field (typo fix), don't teleport them away.
    const wasEmpty = !(values[varName] ?? "").trim();

    setValues((prev) => ({ ...prev, [varName]: val }));

    if (!wasEmpty) {
      setEditingInstance(null);
      return;
    }

    const nextInstance = allInstances.find(({ varName: vn }) => {
      if (vn === varName) return false;
      return (values[vn] ?? "").trim().length === 0;
    });

    if (!nextInstance) {
      setEditingInstance(null);
      return;
    }

    requestAnimationFrame(() => {
      const el = pillRefs.current.get(nextInstance.instanceKey);
      if (el) el.scrollIntoView({ behavior: "smooth", block: "center" });
      setEditingInstance(nextInstance.instanceKey);
    });
  }, [allInstances, values]);

  const handleOpen = useCallback((instanceKey: InstanceKey) => {
    setEditingInstance(instanceKey);
  }, []);

  const handleClose = useCallback(() => {
    setEditingInstance(null);
  }, []);

  const registerPill = useCallback(
    (instanceKey: InstanceKey, el: HTMLButtonElement | null) => {
      if (el) {
        pillRefs.current.set(instanceKey, el);
      } else {
        pillRefs.current.delete(instanceKey);
      }
    },
    []
  );

  /** Generate the document. */
  const handleGenerate = async () => {
    try {
      const result = await generateMutation.mutateAsync({
        template_version_id: templateVersionId,
        variables: values,
      });
      setDocumentId(result.id);
      setFileName(result.docx_file_name);
      toast.success("¡Documento generado con éxito!");
    } catch {
      toast.error("Error al generar el documento");
    }
  };

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div className="flex flex-col gap-0">
      {/* ── Header ── */}
      <div className="flex items-center justify-between mb-1">
        <div>
          <h2 className="text-base font-semibold text-[#191c1e]">
            Llenar documento
          </h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            {templateName}
          </p>
        </div>
        <span className="text-xs font-medium text-muted-foreground whitespace-nowrap">
          {filledCount} de {totalCount} completos
        </span>
      </div>

      {/* ── Progress bar ── */}
      <Progress
        value={filledCount}
        max={totalCount || 1}
        className="h-1.5 mb-5 bg-blue-100 [&>div]:bg-gradient-to-r [&>div]:from-[#004ac6] [&>div]:to-[#2563eb]"
      />

      {/* ── Document body ── */}
      <div
        className={cn(
          "rounded-xl border border-border/50 bg-white",
          "shadow-[0_4px_16px_rgba(25,28,30,0.06)]",
          "px-8 py-8 space-y-5",
          "max-w-3xl w-full mx-auto",
        )}
      >
        {paragraphs.map((para, idx) => (
          <Fragment key={para.id}>
            {idx > 0 && (
              <div
                aria-hidden="true"
                className="text-center text-gray-300 text-lg tracking-[0.6em] select-none py-1"
              >
                · · ·
              </div>
            )}
            <ParagraphRenderer
              paragraph={para}
              values={values}
              editingInstance={editingInstance}
              onSegmentOpen={handleOpen}
              onSegmentClose={handleClose}
              onCommit={handleCommit}
              registerPill={registerPill}
            />
          </Fragment>
        ))}
      </div>

      {/* ── Footer ── */}
      <div className="flex items-center justify-end mt-6">
        <Button
          type="button"
          disabled={!allFilled || generateMutation.isPending}
          onClick={handleGenerate}
          className="bg-gradient-to-br from-[#004ac6] to-[#2563eb] text-white shadow-[0_4px_12px_rgba(0,74,198,0.3)] hover:shadow-[0_6px_20px_rgba(0,74,198,0.4)] transition-all disabled:opacity-50"
        >
          {generateMutation.isPending ? "Generando..." : "Generar documento"}
        </Button>
      </div>

      {/* ── Success panel ── */}
      {documentId && (
        <div className="mt-5 rounded-lg border-0 p-5 bg-[#d1fae5] shadow-[0_4px_16px_rgba(5,150,105,0.1)]">
          <h3 className="font-semibold mb-2 text-[#065f46]">Documento Listo</h3>
          <p className="text-sm text-[#047857] mb-3">
            Su documento &quot;{fileName}&quot; ha sido generado.
          </p>
          <DownloadButton
            documentId={documentId}
            baseFileName={fileName}
            via="direct"
          />
        </div>
      )}
    </div>
  );
}
