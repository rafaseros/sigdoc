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
import { Select as BaseSelect } from "@base-ui/react/select";
import { Check, ChevronDown, CircleCheck, Sparkles } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { DownloadButton } from "./DownloadButton";
import { useGenerateDocument } from "../api/mutations";
import {
  assembleDocument,
  type VariableMeta,
  type VariableType,
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
  /** Variable type — controls which input is rendered in the popover */
  varType?: VariableType;
  /** Predefined options for type="select" */
  varOptions?: string[] | null;
  /** Optional hint shown to the user filling the document */
  varHelpText?: string | null;
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
  varType = "text",
  varOptions,
  varHelpText,
}: PlaceholderWidgetProps) {
  const [draft, setDraft] = useState(value);
  const inputRef = useRef<HTMLInputElement | null>(null);
  // Stable ref for the pill button — used as anchor for the positioner
  const pillButtonRef = useRef<HTMLButtonElement | null>(null);
  const label = humanLabel(varName);
  const isFilled = value.trim().length > 0;

  // Sync draft when popover opens + auto-focus input
  useEffect(() => {
    if (isEditing) {
      setDraft(value);
      if (varType !== "select") {
        requestAnimationFrame(() => {
          inputRef.current?.focus();
        });
      }
    }
  }, [isEditing, value, varType]);

  function handleCommit() {
    const trimmed = draft.trim();
    if (trimmed) {
      onCommit(trimmed);
    }
    onClose();
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter") {
      e.preventDefault();
      handleCommit();
    }
    if (e.key === "Escape") {
      onClose();
    }
  }

  /** When the user picks a select option, commit immediately and close. */
  function handleSelectCommit(val: string) {
    if (val) {
      onCommit(val);
    }
    onClose();
  }

  // instanceKey is used by the parent for identity — not needed in JSX directly,
  // but we keep it in props so TypeScript enforces the caller passes it.
  void instanceKey;

  const inputId = `popover-input-${varName}`;

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
          "inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-sm font-medium transition-all cursor-pointer select-none",
          "align-baseline mx-0.5 whitespace-normal",
          isFilled
            ? "bg-gradient-to-br from-[#fef3c7] to-[#fde68a] text-[#78350f] border border-solid border-[#f59e0b] font-semibold shadow-[0_1px_3px_rgba(245,158,11,0.25)] hover:shadow-[0_2px_6px_rgba(245,158,11,0.35)] hover:from-[#fde68a] hover:to-[#fcd34d]"
            : "bg-[var(--bg-accent)] text-[var(--primary)] border border-dashed border-[#2563eb]/40 hover:bg-[#c7d2fe] hover:border-[#2563eb]/70",
          isEditing &&
            "ring-2 ring-[#2563eb]/60 ring-offset-1 ring-offset-white",
        )}
      >
        {!isFilled && (
          <span className="text-[#2563eb] font-bold text-xs leading-none">
            +
          </span>
        )}
        <span>{isFilled ? value : label}</span>
      </button>

      {/* Controlled popover anchored to the pill — no Popover.Trigger needed
          because we provide an explicit anchor on Popover.Positioner and drive
          open state from props. */}
      <Popover.Root
        open={isEditing}
        onOpenChange={(open) => {
          if (!open) onClose();
        }}
      >
        <Popover.Portal>
          <Popover.Positioner
            anchor={pillButtonRef}
            side="bottom"
            align="start"
            sideOffset={6}
          >
            <Popover.Popup
              className={cn(
                "z-50 w-72 rounded-xl bg-white p-4 ring-1 ring-[rgba(195,198,215,0.30)]",
                "shadow-[var(--shadow-lg)]",
                "outline-none",
              )}
            >
              <Label
                htmlFor={inputId}
                className="block text-[11px] font-semibold uppercase tracking-[0.04em] text-[var(--fg-3)] mb-2"
              >
                {label}
              </Label>

              {varHelpText && (
                <p className="text-[12px] text-[var(--fg-3)] italic mb-2">
                  {varHelpText}
                </p>
              )}

              {/* ── Select input ── */}
              {varType === "select" && varOptions && varOptions.length > 0 ? (
                <BaseSelect.Root
                  // Pass `null` (Base UI's "no selection" sentinel) when draft
                  // is empty. Using `undefined` here would flip the component
                  // from uncontrolled → controlled on first selection and
                  // trigger Base UI's controlled-state warning.
                  value={draft || null}
                  onValueChange={(val) => {
                    if (!val) return;
                    setDraft(val);
                    // Auto-commit on selection for a friction-free flow
                    handleSelectCommit(val);
                  }}
                >
                  <BaseSelect.Trigger
                    id={inputId}
                    className={cn(
                      "flex w-full items-center justify-between gap-2 rounded-lg border border-input bg-[var(--bg-muted)] px-3 py-2 text-sm",
                      "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#2563eb]/50",
                      "data-placeholder:text-[var(--fg-3)]",
                    )}
                  >
                    <BaseSelect.Value placeholder={`Seleccione ${label}`} />
                    <BaseSelect.Icon
                      render={
                        <ChevronDown className="size-4 text-[var(--fg-3)] shrink-0" />
                      }
                    />
                  </BaseSelect.Trigger>
                  <BaseSelect.Portal>
                    <BaseSelect.Positioner
                      side="bottom"
                      sideOffset={4}
                      className="isolate z-[60]"
                    >
                      <BaseSelect.Popup
                        className={cn(
                          "max-h-56 w-(--anchor-width) min-w-32 overflow-y-auto rounded-lg",
                          "bg-popover text-popover-foreground shadow-md ring-1 ring-foreground/10",
                          "origin-(--transform-origin)",
                          "data-open:animate-in data-open:fade-in-0 data-open:zoom-in-95",
                          "data-closed:animate-out data-closed:fade-out-0 data-closed:zoom-out-95",
                        )}
                      >
                        <BaseSelect.List className="p-1">
                          {varOptions.map((opt) => (
                            <BaseSelect.Item
                              key={opt}
                              value={opt}
                              className={cn(
                                "relative flex w-full cursor-default items-center gap-1.5 rounded-md py-1 pr-8 pl-1.5",
                                "text-sm outline-hidden select-none",
                                "focus:bg-accent focus:text-accent-foreground",
                                "data-disabled:pointer-events-none data-disabled:opacity-50",
                              )}
                            >
                              <BaseSelect.ItemText className="flex-1">
                                {opt}
                              </BaseSelect.ItemText>
                              <BaseSelect.ItemIndicator
                                render={
                                  <span className="pointer-events-none absolute right-2 flex size-4 items-center justify-center" />
                                }
                              >
                                <Check className="size-3.5" />
                              </BaseSelect.ItemIndicator>
                            </BaseSelect.Item>
                          ))}
                        </BaseSelect.List>
                      </BaseSelect.Popup>
                    </BaseSelect.Positioner>
                  </BaseSelect.Portal>
                </BaseSelect.Root>
              ) : (
                /* ── Text / integer / decimal input ── */
                <div className="relative">
                  <Input
                    id={inputId}
                    ref={inputRef}
                    type={varType === "integer" || varType === "decimal" ? "number" : "text"}
                    step={varType === "decimal" ? "any" : varType === "integer" ? "1" : undefined}
                    inputMode={
                      varType === "integer"
                        ? "numeric"
                        : varType === "decimal"
                        ? "decimal"
                        : undefined
                    }
                    value={draft}
                    onChange={(e) => setDraft(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder={`Ingrese ${label}`}
                    className="bg-[var(--bg-muted)] border-transparent focus:border-[#2563eb] focus:ring-[#2563eb]/20 pr-10 text-sm"
                  />
                  {/* ↵ Enter hint */}
                  <span className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 text-[10px] text-[var(--fg-3)]/60 font-mono">
                    ↵
                  </span>
                </div>
              )}

              {/* Footer buttons — hidden for select (auto-commits on pick) */}
              {varType !== "select" && (
                <div className="mt-3 flex justify-end gap-2">
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={onClose}
                    className="text-xs text-[var(--fg-2)]"
                  >
                    Cancelar
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    onClick={handleCommit}
                    className="text-xs bg-gradient-to-br from-[#004ac6] to-[#2563eb] font-semibold text-white shadow-[var(--shadow-brand-sm)] hover:shadow-[var(--shadow-brand-md)]"
                  >
                    Confirmar
                  </Button>
                </div>
              )}
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
  /** Map from variable name → VariableMeta for type/options lookup */
  metaByName: Record<string, VariableMeta>;
}

function ParagraphRenderer({
  paragraph,
  values,
  editingInstance,
  onSegmentOpen,
  onSegmentClose,
  onCommit,
  registerPill,
  metaByName,
}: ParagraphRendererProps) {
  return (
    <p className="text-[15px] leading-8 text-[var(--fg-1)] font-serif">
      {paragraph.segments.map((seg: DocumentSegment, i: number) => {
        if (seg.type === "text") {
          return <span key={i}>{seg.content}</span>;
        }
        const varName = seg.content;
        const instanceKey: InstanceKey = `${paragraph.id}::${i}`;
        const meta = metaByName[varName];
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
            varType={meta?.type ?? "text"}
            varOptions={meta?.options}
            varHelpText={meta?.help_text}
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

  // Map from variable name → VariableMeta for O(1) type/options lookup in renderers
  const metaByName = useMemo(
    () => Object.fromEntries(variablesMeta.map((m) => [m.name, m])),
    [variablesMeta]
  );

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

  const remaining = totalCount - filledCount;

  return (
    <div className="flex flex-col gap-0">
      {/* ── Header (progress) ── */}
      <div className="mb-3 rounded-xl bg-white p-4 shadow-[var(--shadow-sm)] ring-1 ring-[rgba(195,198,215,0.30)]">
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0">
            <div className="sd-meta">Completar variables</div>
            <p className="mt-0.5 truncate text-[13px] text-[var(--fg-3)]">
              {templateName}
            </p>
          </div>
          <span className="whitespace-nowrap text-[13px] font-semibold text-[var(--fg-1)]">
            {filledCount} <span className="text-[var(--fg-3)]">/</span>{" "}
            {totalCount}
          </span>
        </div>
        <Progress
          value={filledCount}
          max={totalCount || 1}
          className="mt-3 h-1.5 bg-[var(--bg-muted)] [&>div]:bg-gradient-to-r [&>div]:from-[#004ac6] [&>div]:to-[#2563eb]"
        />
      </div>

      {/* ── Document body ── */}
      <div
        className={cn(
          "rounded-xl bg-white",
          "shadow-[var(--shadow-md)] ring-1 ring-[rgba(195,198,215,0.30)]",
          "px-8 py-8 space-y-5",
          "max-w-3xl w-full mx-auto",
        )}
      >
        {paragraphs.map((para, idx) => (
          <Fragment key={para.id}>
            {idx > 0 && (
              <div
                aria-hidden="true"
                className="select-none py-1 text-center text-lg tracking-[0.6em] text-[rgba(195,198,215,0.60)]"
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
              metaByName={metaByName}
            />
          </Fragment>
        ))}
      </div>

      {/* ── Sticky save bar ── */}
      <div className="sticky bottom-0 z-10 mt-5 flex flex-wrap items-center justify-between gap-3 rounded-xl bg-white/90 px-4 py-3 shadow-[var(--shadow-md)] ring-1 ring-[rgba(195,198,215,0.30)] backdrop-blur">
        <div className="text-[12.5px] text-[var(--fg-3)]">
          {allFilled ? (
            <span className="inline-flex items-center gap-1.5 font-medium text-[#065f46]">
              <CircleCheck className="size-4 text-[#059669]" />
              Listo para generar
            </span>
          ) : (
            <>
              Faltan{" "}
              <span className="font-semibold text-[var(--fg-1)]">
                {remaining}
              </span>{" "}
              variable{remaining === 1 ? "" : "s"}
            </>
          )}
        </div>
        <Button
          type="button"
          disabled={!allFilled || generateMutation.isPending}
          onClick={handleGenerate}
          className="bg-gradient-to-br from-[#004ac6] to-[#2563eb] font-semibold text-white shadow-[var(--shadow-brand-sm)] hover:shadow-[var(--shadow-brand-md)] transition-all disabled:opacity-50"
        >
          <Sparkles className="size-4" />
          {generateMutation.isPending ? "Generando..." : "Generar documento"}
        </Button>
      </div>

      {/* ── Success panel ── */}
      {documentId && (
        <div className="mt-5 rounded-xl bg-[#d1fae5] p-5 shadow-[0_4px_16px_rgba(5,150,105,0.10)]">
          <div className="mb-2 flex items-center gap-2">
            <CircleCheck className="size-4 text-[#059669]" />
            <h3 className="m-0 text-[14px] font-bold text-[#065f46]">
              Documento listo
            </h3>
          </div>
          <p className="mb-3 text-[13px] text-[#047857]">
            Su documento &quot;{fileName}&quot; ha sido generado correctamente.
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
