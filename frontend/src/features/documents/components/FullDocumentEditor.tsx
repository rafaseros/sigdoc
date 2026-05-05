/**
 * FullDocumentEditor.tsx
 *
 * Renders the complete .docx as a paginated document with three sections —
 * Encabezado / Contenido / Pie de página — and lets the user fill every
 * `{{ variable }}` placeholder inline through a popover.
 *
 * Powered by GET /api/v1/templates/{tid}/versions/{vid}/structure.
 *
 * Auto-jump: every placeholder occurrence is tracked as a unique "instance"
 * (key derived from its position). Committing a value advances the editor
 * to the next pending instance and opens its popover.
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
  useMemo,
  useRef,
  useState,
} from "react";
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
  const filled = value.trim().length > 0;
  const label = humanLabel(varName);
  const type: VariableType = meta?.type ?? "text";
  const options = meta?.options ?? null;

  const handleOpenChange = (next: boolean) => {
    if (next) setDraft(value);
    onOpenChange(key, next);
  };

  const commit = (raw: string) => {
    onCommit(key, varName, raw.trim());
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
                    onOpenChange(key, false);
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
                onClick={() => onOpenChange(key, false)}
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
});

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
        // Defer parent commit by one frame: the BaseSelect needs to finish
        // its close + focus-restore cycle before the outer Popover unmounts.
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

  const metaByName = useMemo(
    () => Object.fromEntries(variablesMeta.map((m) => [m.name, m])),
    [variablesMeta],
  );

  const generateMutation = useGenerateDocument();

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
    (key, varName, value) => {
      const scrollY = window.scrollY;
      setValues((prev) => ({ ...prev, [varName]: value }));

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

      requestAnimationFrame(() => {
        if (Math.abs(window.scrollY - scrollY) > 4) {
          window.scrollTo({ top: scrollY, behavior: "instant" });
        }
      });
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
