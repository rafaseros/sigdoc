/**
 * FullDocumentEditor.tsx
 *
 * Renders the complete .docx as a paginated document with three sections —
 * Encabezado / Contenido / Pie de página — and lets the user fill every
 * `{{ variable }}` placeholder inline: clicking a pill swaps it, in place,
 * for a text/select control (no popover, no portal — see PlaceholderPill).
 *
 * Powered by GET /api/v1/templates/{tid}/versions/{vid}/structure.
 *
 * Auto-jump: every placeholder occurrence is tracked as a unique "instance"
 * (key derived from its position). Committing a value via Enter (or picking
 * a select option) advances the editor to the next pending instance and
 * swaps its pill for a control; committing via blur does not advance.
 *
 * Performance:
 * - PlaceholderPill is wrapped in React.memo so a commit on one pill does
 *   not re-render the other 200/500/1000 pills in the document.
 * - Parent callbacks are stabilised with useCallback + a ref to the latest
 *   `values` so the pills can compare props by identity.
 */

import {
  Fragment,
  memo,
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import type { RefObject } from "react";
import { Select as BaseSelect } from "@base-ui/react/select";
import { Check, ChevronDown, Eye, FileText, Sparkles } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Progress } from "@/components/ui/progress";

import { useGenerateDocument, usePreviewDocument } from "../api/mutations";
import { DownloadButton } from "./DownloadButton";

import type {
  StructureNode,
  StructureSpan,
  StructureTableCell as StructureTableCellType,
  TemplateStructure,
} from "@/features/templates/api/queries";
import type {
  VariableMeta,
  VariableType,
} from "@/features/templates/api/queries";

// ---------------------------------------------------------------------------
// Props / types
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

interface PlaceholderInstance {
  key: string;
  varName: string;
}

type CommitHandler = (
  instanceKey: string,
  varName: string,
  value: string,
  advance: boolean,
) => void;
type OpenChangeHandler = (instanceKey: string, open: boolean) => void;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function humanLabel(name: string): string {
  return name.replace(/_/g, " ");
}

function instanceKey(prefix: string, ...indices: number[]): string {
  return `${prefix}-${indices.join("-")}`;
}

function visitNodeForInstances(
  node: StructureNode,
  prefix: string,
  out: PlaceholderInstance[],
): void {
  if (node.kind === "table") {
    node.rows.forEach((row, rowIdx) => {
      row.cells.forEach((cell, cellIdx) => {
        cell.nodes.forEach((child, childIdx) => {
          visitNodeForInstances(
            child,
            instanceKey(prefix, rowIdx, cellIdx, childIdx),
            out,
          );
        });
      });
    });
    return;
  }
  node.spans.forEach((span, spanIdx) => {
    if (span.variable) {
      out.push({
        key: instanceKey(prefix, spanIdx),
        varName: span.variable,
      });
    }
  });
}

function collectInstances(structure: TemplateStructure): PlaceholderInstance[] {
  const out: PlaceholderInstance[] = [];
  structure.headers.forEach((node, i) =>
    visitNodeForInstances(node, instanceKey("h", i), out),
  );
  structure.body.forEach((node, i) =>
    visitNodeForInstances(node, instanceKey("b", i), out),
  );
  structure.footers.forEach((node, i) =>
    visitNodeForInstances(node, instanceKey("f", i), out),
  );
  return out;
}

// ---------------------------------------------------------------------------
// PlaceholderPill — memoized so commits on one pill don't re-render the rest
// ---------------------------------------------------------------------------

/** Clamp the inline control's `ch`-based width to a sensible range. */
function inputWidthCh(draftLength: number, placeholderLength: number): number {
  return Math.min(Math.max(draftLength, placeholderLength, 3), 40);
}

interface PlaceholderPillProps {
  instanceKey: string;
  varName: string;
  value: string;
  meta: VariableMeta | undefined;
  isEditing: boolean;
  onOpenChange: OpenChangeHandler;
  onCommit: CommitHandler;
}

const PlaceholderPill = memo(function PlaceholderPill({
  instanceKey: key,
  varName,
  value,
  meta,
  isEditing,
  onOpenChange,
  onCommit,
}: PlaceholderPillProps) {
  const [draft, setDraft] = useState(value);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const suppressBlurRef = useRef(false);
  // Select-only guards (see InlineSelectInput): dropdownOpenRef tracks
  // whether the listbox is currently open, committedRef tracks whether a
  // value was committed during this editing session. Both live here (the
  // editing-session owner) rather than inside InlineSelectInput so they
  // reset in lockstep with suppressBlurRef every time editing (re-)starts.
  const dropdownOpenRef = useRef(false);
  const committedRef = useRef(false);
  const filled = value.trim().length > 0;
  const label = humanLabel(varName);
  const type: VariableType = meta?.type ?? "text";
  const options = meta?.options ?? null;
  const helpText = meta?.help_text ?? null;
  const placeholder = helpText || varName;

  // This component is never remounted while swapping pill <-> input (memo
  // boundary keeps typing from re-rendering sibling pills) — re-sync `draft`
  // from the shared, name-keyed committed value every time this instance
  // (re-)enters edit mode. Also reset the blur-suppression guard here: it's
  // only meant to swallow the single spurious blur that *may* fire when
  // Enter/Escape unmount the input, and some environments never fire that
  // event at all — resetting on every fresh edit prevents a stale `true`
  // from silently discarding a later, genuine blur-commit.
  useLayoutEffect(() => {
    if (isEditing) {
      setDraft(value);
      suppressBlurRef.current = false;
      dropdownOpenRef.current = false;
      committedRef.current = false;
    }
  }, [isEditing, value]);

  // Focus the swapped-in control synchronously (before paint) without
  // scrolling the page — this replaces the old triple/uncoordinated focus
  // calls (Popover auto-focus + native autoFocus) that raced floating-ui's
  // positioning and caused the scroll-to-top jump.
  useLayoutEffect(() => {
    if (isEditing && type !== "select") {
      inputRef.current?.focus({ preventScroll: true });
      inputRef.current?.scrollIntoView({ block: "nearest" });
    }
  }, [isEditing, type]);

  const commit = (raw: string, advance: boolean) => {
    onCommit(key, varName, raw.trim(), advance);
  };

  const cancel = () => {
    setDraft(value);
    onOpenChange(key, false);
  };

  if (!isEditing) {
    return (
      <button
        type="button"
        data-instance-key={key}
        onClick={() => onOpenChange(key, true)}
        className={`var-chip ${filled ? "var-chip-active" : "var-chip-muted"} cursor-pointer hover:brightness-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]`}
        title={helpText ?? `Editar: ${label}`}
      >
        {filled ? value : `{{ ${varName} }}`}
      </button>
    );
  }

  if (type === "select" && options && options.length > 0) {
    return (
      <InlineSelectInput
        instanceKey={key}
        value={draft}
        options={options}
        placeholder={placeholder}
        helpText={helpText}
        onCommit={(v) => commit(v, true)}
        onCancel={cancel}
        dropdownOpenRef={dropdownOpenRef}
        committedRef={committedRef}
      />
    );
  }

  const widthCh = inputWidthCh(draft.length, placeholder.length);

  return (
    <input
      ref={inputRef}
      type="text"
      data-instance-key={key}
      value={draft}
      onChange={(e) => setDraft(e.target.value)}
      onKeyDown={(e) => {
        if (e.key === "Enter") {
          if (e.nativeEvent.isComposing) return;
          e.preventDefault();
          suppressBlurRef.current = true;
          commit(draft, true);
        } else if (e.key === "Escape") {
          e.preventDefault();
          suppressBlurRef.current = true;
          cancel();
        }
      }}
      onBlur={() => {
        if (suppressBlurRef.current) {
          suppressBlurRef.current = false;
          return;
        }
        commit(draft, false);
      }}
      inputMode={
        type === "integer"
          ? "numeric"
          : type === "decimal"
            ? "decimal"
            : "text"
      }
      placeholder={placeholder}
      title={helpText ?? undefined}
      className="mx-0.5 max-w-full min-w-0 rounded-md border border-[#2563eb]/50 bg-white px-1.5 py-px align-baseline font-mono text-[11.5px] text-[var(--fg-1)] outline-none ring-2 ring-[#2563eb]/30 focus:ring-[#2563eb]/50"
      style={{ width: `${widthCh}ch` }}
    />
  );
});

function InlineSelectInput({
  instanceKey: key,
  value,
  options,
  placeholder,
  helpText,
  onCommit,
  onCancel,
  dropdownOpenRef,
  committedRef,
}: {
  instanceKey: string;
  value: string;
  options: string[];
  placeholder: string;
  helpText: string | null;
  onCommit: (v: string) => void;
  onCancel: () => void;
  dropdownOpenRef: RefObject<boolean>;
  committedRef: RefObject<boolean>;
}) {
  const triggerRef = useRef<HTMLButtonElement | null>(null);

  useLayoutEffect(() => {
    triggerRef.current?.focus({ preventScroll: true });
    triggerRef.current?.scrollIntoView({ block: "nearest" });
  }, []);

  return (
    <BaseSelect.Root
      value={value || null}
      onValueChange={(v) => {
        const next = (v as string) ?? "";
        if (next) {
          // Mark committed BEFORE onCommit: the parent may synchronously
          // auto-advance editingKey, and the dropdown-close/blur that follows
          // this selection must not fire a stale onCancel against that new
          // editing state.
          committedRef.current = true;
          onCommit(next);
        }
      }}
      onOpenChange={(open) => {
        dropdownOpenRef.current = open;
        // Closing the listbox without having selected a value means the
        // user clicked away (or dismissed it) — revert to the pill instead
        // of leaving this select stuck open-looking forever.
        if (!open && !committedRef.current) onCancel();
      }}
    >
      <BaseSelect.Trigger
        ref={triggerRef}
        data-instance-key={key}
        title={helpText ?? undefined}
        onKeyDown={(e) => {
          if (e.key === "Escape") {
            e.preventDefault();
            onCancel();
          }
        }}
        onBlur={() => {
          // Clicking away from a focused trigger whose dropdown never
          // opened also needs to revert. Do NOT cancel while the dropdown
          // is open: opening the listbox moves focus off the trigger, and
          // treating that as a blur-cancel would abort mid-selection.
          if (!dropdownOpenRef.current && !committedRef.current) onCancel();
        }}
        className="mx-0.5 inline-flex max-w-full items-center gap-1 rounded-md border border-[#2563eb]/50 bg-white px-1.5 py-px align-baseline font-mono text-[11.5px] text-[var(--fg-1)] outline-none ring-2 ring-[#2563eb]/30"
      >
        <BaseSelect.Value placeholder={placeholder} />
        <ChevronDown className="size-3 text-[var(--fg-3)]" />
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
// Block renderers — text, list, table
// ---------------------------------------------------------------------------

interface NodeRendererProps {
  node: StructureNode;
  prefix: string;
  values: Record<string, string>;
  metaByName: Record<string, VariableMeta>;
  editingKey: string | null;
  onOpenChange: OpenChangeHandler;
  onCommit: CommitHandler;
}

function DocumentNode(props: NodeRendererProps) {
  const { node, prefix } = props;
  if (node.kind === "table") {
    return <TableNode {...props} />;
  }
  if (node.kind === "list_bullet" || node.kind === "list_number") {
    return <ListItemNode {...props} />;
  }
  // paragraph or heading
  return <TextNode {...props} key={prefix} />;
}

function renderSpans(
  spans: StructureSpan[],
  prefix: string,
  values: Record<string, string>,
  metaByName: Record<string, VariableMeta>,
  editingKey: string | null,
  onOpenChange: OpenChangeHandler,
  onCommit: CommitHandler,
) {
  return spans.map((span: StructureSpan, spanIdx) => {
    if (!span.variable) {
      return <Fragment key={spanIdx}>{span.text}</Fragment>;
    }
    const key = instanceKey(prefix, spanIdx);
    return (
      <PlaceholderPill
        key={key}
        instanceKey={key}
        varName={span.variable}
        value={values[span.variable] ?? ""}
        meta={metaByName[span.variable]}
        isEditing={editingKey === key}
        onOpenChange={onOpenChange}
        onCommit={onCommit}
      />
    );
  });
}

function TextNode({
  node,
  prefix,
  values,
  metaByName,
  editingKey,
  onOpenChange,
  onCommit,
}: NodeRendererProps) {
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
      {renderSpans(
        node.spans,
        prefix,
        values,
        metaByName,
        editingKey,
        onOpenChange,
        onCommit,
      )}
    </p>
  );
}

function ListItemNode({
  node,
  prefix,
  values,
  metaByName,
  editingKey,
  onOpenChange,
  onCommit,
}: NodeRendererProps) {
  const isBullet = node.kind === "list_bullet";
  const indent = Math.max(node.level, 1);
  // Visual marker — for numbered lists we don't have the original index from
  // the .docx (Word numbers them via field codes, not run text), so we use a
  // generic "1." marker that signals it's a numbered item without lying about
  // the order.
  const marker = isBullet ? "•" : "1.";
  return (
    <p
      className="my-1 flex gap-2 text-[14px] leading-[1.7] text-[var(--fg-1)]"
      style={{ paddingLeft: `${(indent - 1) * 16 + 12}px` }}
    >
      <span
        className={`shrink-0 ${isBullet ? "w-3 text-[var(--fg-3)]" : "w-5 font-medium tabular-nums text-[var(--fg-3)]"}`}
      >
        {marker}
      </span>
      <span className="flex-1">
        {renderSpans(
          node.spans,
          prefix,
          values,
          metaByName,
          editingKey,
          onOpenChange,
          onCommit,
        )}
      </span>
    </p>
  );
}

function TableNode({
  node,
  prefix,
  values,
  metaByName,
  editingKey,
  onOpenChange,
  onCommit,
}: NodeRendererProps) {
  return (
    <div className="my-3 overflow-x-auto">
      <table className="w-full border-collapse text-[13px]">
        <tbody>
          {node.rows.map((row, rowIdx) => (
            <tr
              key={`${prefix}-r${rowIdx}`}
              className="border-b border-[rgba(195,198,215,0.30)] last:border-b-0"
            >
              {row.cells.map((cell: StructureTableCellType, cellIdx) => (
                <td
                  key={`${prefix}-r${rowIdx}-c${cellIdx}`}
                  className="border-l border-[rgba(195,198,215,0.20)] px-2.5 py-1.5 align-top first:border-l-0"
                >
                  {cell.nodes.length === 0 ? (
                    <span className="text-[var(--fg-3)]">—</span>
                  ) : (
                    cell.nodes.map((child, childIdx) => (
                      <DocumentNode
                        key={`${prefix}-r${rowIdx}-c${cellIdx}-${childIdx}`}
                        node={child}
                        prefix={instanceKey(
                          prefix,
                          rowIdx,
                          cellIdx,
                          childIdx,
                        )}
                        values={values}
                        metaByName={metaByName}
                        editingKey={editingKey}
                        onOpenChange={onOpenChange}
                        onCommit={onCommit}
                      />
                    ))
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
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
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  const metaByName = useMemo(
    () => Object.fromEntries(variablesMeta.map((m) => [m.name, m])),
    [variablesMeta],
  );

  const generateMutation = useGenerateDocument();
  const previewMutation = usePreviewDocument();

  // Blob URL lifecycle: keep a ref in sync with the latest URL so the
  // unmount cleanup below always revokes the most recent one, without
  // re-registering the cleanup effect on every preview.
  const previewUrlRef = useRef<string | null>(null);
  useEffect(() => {
    previewUrlRef.current = previewUrl;
  }, [previewUrl]);

  // Preview request lifecycle guards:
  // - previewRequestIdRef identifies the "current" preview request. Closing
  //   the dialog (or starting a new preview) bumps it, so a stale in-flight
  //   request's callbacks can detect they've been superseded and no-op
  //   instead of flashing an outdated PDF into a reopened dialog.
  // - isMountedRef guards against setState / object-URL creation after this
  //   component has unmounted mid-request.
  const previewRequestIdRef = useRef(0);
  const isMountedRef = useRef(true);

  useEffect(() => {
    return () => {
      isMountedRef.current = false;
      if (previewUrlRef.current) {
        URL.revokeObjectURL(previewUrlRef.current);
      }
    };
  }, []);

  // Keep a ref to the latest `values` so the memoized commit callback can
  // read the freshest state without invalidating its identity.
  const valuesRef = useRef(values);
  useEffect(() => {
    valuesRef.current = values;
  }, [values]);

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

  const handleOpenChange = useCallback<OpenChangeHandler>((key, open) => {
    setEditingKey((current) => {
      if (open) return key;
      return current === key ? null : current;
    });
  }, []);

  const handleCommit = useCallback<CommitHandler>(
    (key, varName, value, advance) => {
      setValues((prev) => ({ ...prev, [varName]: value }));

      if (!advance) {
        setEditingKey(null);
        return;
      }

      // Find next pending instance using the post-commit values snapshot.
      const nextValues = { ...valuesRef.current, [varName]: value };
      const startIdx = instances.findIndex((i) => i.key === key);
      let nextKey: string | null = null;
      if (startIdx !== -1) {
        for (let i = startIdx + 1; i < instances.length; i++) {
          const inst = instances[i];
          if (!nextValues[inst.varName] || nextValues[inst.varName].trim() === "") {
            nextKey = inst.key;
            break;
          }
        }
      }
      setEditingKey(nextKey);
    },
    [instances],
  );

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

  const handlePreview = () => {
    setPreviewOpen(true);
    // Revoke + clear any previous preview FIRST so the dialog always shows
    // the loading placeholder while a new request is in flight — it must
    // never keep rendering a stale PDF from a prior request.
    setPreviewUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev);
      return null;
    });
    const requestId = ++previewRequestIdRef.current;
    previewMutation.mutate(
      { template_version_id: templateVersionId, variables: values },
      {
        onSuccess: (data) => {
          const newUrl = URL.createObjectURL(
            new Blob([data], { type: "application/pdf" }),
          );
          // This request may have been superseded (dialog closed and/or a
          // newer preview started) or the component may have unmounted
          // while the request was in flight — either way, discard the blob
          // without ever setting state.
          if (
            !isMountedRef.current ||
            requestId !== previewRequestIdRef.current
          ) {
            URL.revokeObjectURL(newUrl);
            return;
          }
          setPreviewUrl(newUrl);
        },
        onError: () => {
          if (!isMountedRef.current) return;
          toast.error("Error al generar la vista previa");
          setPreviewOpen(false);
        },
      },
    );
  };

  const handlePreviewOpenChange = (open: boolean) => {
    setPreviewOpen(open);
    if (!open) {
      // Invalidate any preview request still in flight so its eventual
      // onSuccess/onError treats itself as stale.
      previewRequestIdRef.current++;
      setPreviewUrl((prev) => {
        if (prev) URL.revokeObjectURL(prev);
        return null;
      });
    }
  };

  const handleVariableRowClick = useCallback(
    (varName: string) => {
      const inst = instances.find((i) => i.varName === varName);
      if (!inst) return;
      setEditingKey(inst.key);
      requestAnimationFrame(() => {
        document
          .querySelector<HTMLElement>(`[data-instance-key="${inst.key}"]`)
          ?.scrollIntoView({ block: "center" });
      });
    },
    [instances],
  );

  const hasHeaders = structure.headers.length > 0;
  const hasFooters = structure.footers.length > 0;

  const sectionProps = {
    values,
    metaByName,
    editingKey,
    onOpenChange: handleOpenChange,
    onCommit: handleCommit,
  };

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_280px]">
      <div className="flex min-w-0 flex-col gap-4">
        {/* Top progress card */}
        <div className="rounded-xl bg-white p-4 shadow-[var(--shadow-sm)] ring-1 ring-[rgba(195,198,215,0.30)]">
          <div className="mb-2">
            <div className="text-[13px] font-semibold text-[var(--fg-1)]">
              Progreso de la generación
            </div>
            <div className="text-[11.5px] text-[var(--fg-3)]">
              {filledCount} de {totalCount} variable
              {totalCount === 1 ? "" : "s"} completada
              {filledCount === 1 ? "" : "s"}
            </div>
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

          {/* pb-16 (instead of a symmetric py-5) leaves clearance so the
              last content line can scroll clear of the sticky action bar
              below, instead of ending flush against it. */}
          <div className="px-6 pt-5 pb-16">
            {hasHeaders && (
              <DocumentSection label="Encabezado">
                {structure.headers.map((node, i) => (
                  <DocumentNode
                    key={`h-${i}`}
                    node={node}
                    prefix={instanceKey("h", i)}
                    {...sectionProps}
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
                    prefix={instanceKey("b", i)}
                    {...sectionProps}
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
                    prefix={instanceKey("f", i)}
                    {...sectionProps}
                  />
                ))}
              </DocumentSection>
            )}
          </div>
        </div>

        {/* Sticky bottom action bar */}
        <div className="sticky bottom-0 z-10 flex flex-wrap items-center justify-between gap-3 rounded-xl bg-white/90 px-4 py-3 shadow-[var(--shadow-md)] ring-1 ring-[rgba(195,198,215,0.30)] backdrop-blur">
          <div className="flex min-w-[180px] flex-1 items-center gap-3">
            <div className="shrink-0 text-[12.5px] text-[var(--fg-3)]">
              {filledCount} de {totalCount} variable
              {totalCount === 1 ? "" : "s"} completada
              {filledCount === 1 ? "" : "s"}
            </div>
            <Progress value={progress} className="h-1.5 max-w-[160px] flex-1" />
          </div>
          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={handlePreview}
              disabled={previewMutation.isPending}
            >
              <Eye className="size-3.5" />
              {previewMutation.isPending
                ? "Generando vista previa…"
                : "Vista previa"}
            </Button>
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
        </div>
      </div>

      {/* Variables review panel */}
      <aside className="self-start lg:sticky lg:top-20">
        <div className="rounded-xl bg-white p-4 shadow-[var(--shadow-sm)] ring-1 ring-[rgba(195,198,215,0.30)]">
          <div className="mb-3">
            <div className="text-[13px] font-semibold text-[var(--fg-1)]">
              Variables
            </div>
            <div className="text-[11.5px] text-[var(--fg-3)]">
              {filledCount} de {totalCount} completada
              {filledCount === 1 ? "" : "s"}
            </div>
          </div>
          <ul className="flex flex-col gap-1">
            {distinctVarNames.map((name) => {
              const value = values[name] ?? "";
              const filled = value.trim().length > 0;
              return (
                <li key={name}>
                  <button
                    type="button"
                    onClick={() => handleVariableRowClick(name)}
                    className="flex w-full items-center justify-between gap-2 rounded-lg px-2 py-1.5 text-left transition-colors hover:bg-[var(--bg-page)]"
                  >
                    <span className="flex min-w-0 items-center gap-1.5">
                      {filled && (
                        <Check className="size-3.5 shrink-0 text-[#059669]" />
                      )}
                      <span className="truncate text-[12.5px] font-medium text-[var(--fg-1)]">
                        {humanLabel(name)}
                      </span>
                    </span>
                    {filled ? (
                      <span
                        className="max-w-[110px] truncate text-[11.5px] text-[var(--fg-3)]"
                        title={value}
                      >
                        {value}
                      </span>
                    ) : (
                      <span className="shrink-0 rounded-full bg-[var(--bg-page)] px-2 py-0.5 text-[10.5px] font-medium text-[var(--fg-3)]">
                        Pendiente
                      </span>
                    )}
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      </aside>

      {/* Preview dialog */}
      <Dialog open={previewOpen} onOpenChange={handlePreviewOpenChange}>
        <DialogContent className="sm:max-w-4xl">
          <DialogHeader>
            <DialogTitle>Vista previa del documento</DialogTitle>
          </DialogHeader>
          {previewUrl ? (
            <iframe
              title="Vista previa del documento"
              src={previewUrl}
              className="h-[75vh] w-full rounded-lg"
            />
          ) : (
            <div className="flex h-[75vh] w-full items-center justify-center text-[13px] text-[var(--fg-3)]">
              Generando vista previa…
            </div>
          )}
        </DialogContent>
      </Dialog>
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
    <section className="mt-4 first:mt-0">
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
