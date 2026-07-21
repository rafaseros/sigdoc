/**
 * ExampleMarkingSurface.tsx
 *
 * Shared "mark variables over a filled example document" surface used by
 * BOTH from-example flows:
 *   - CreateFromExamplePage — new template from an example document.
 *   - AttachFromExamplePage — related file for an existing version, with
 *     existing-variable REUSE (the popover suggests the template's current
 *     variables and flags new names as extra fill-in steps at generation).
 *
 * Owns the read-only document renderer (extracted verbatim from
 * CreateFromExamplePage), the text-selection handling and the conversion
 * popover. The mapping LIST state belongs to the caller — this component
 * only proposes additions via onMappingsChange after enforcing the shared
 * business rules (duplicate text, overlap starvation, zero-effective guard).
 */

import { Fragment, useRef, useState } from "react";
import { toast } from "sonner";
import { FileText, Info, X } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

import type {
  StructureNode,
  StructureSpan,
  StructureTableCell,
  TemplateStructure,
} from "../api/queries";
import {
  addMapping,
  countEffectiveOccurrences,
  countOccurrences,
  filterVariableOptions,
  isValidVariableName,
  readParagraphSelection,
  suggestVariableName,
  segmentText,
  type ExistingVariableOption,
  type VariableMapping,
} from "../lib/fromExample";

// ---------------------------------------------------------------------------
// Small helpers
// ---------------------------------------------------------------------------

export function truncateText(text: string, max: number): string {
  return text.length > max ? `${text.slice(0, max - 1)}…` : text;
}

// ---------------------------------------------------------------------------
// Surface — document card + selection + popover
// ---------------------------------------------------------------------------

interface PopoverState {
  text: string;
  count: number;
  /**
   * Occurrences that would SURVIVE the backend's longest-text-first
   * replacement with the existing mappings plus this candidate. 0 while
   * count > 0 means every occurrence is consumed by a longer mapping —
   * confirming would guarantee a 422 missing_texts at submit.
   */
  effectiveCount: number;
  top: number;
  left: number;
}

export function ExampleMarkingSurface({
  file,
  structure,
  mappings,
  onMappingsChange,
  existingVariables,
}: {
  file: File;
  structure: TemplateStructure;
  mappings: VariableMapping[];
  /** Called with the NEW list after a mapping passes every guard. */
  onMappingsChange: (mappings: VariableMapping[]) => void;
  /** Reuse options (attach flow). When provided, the popover lists them as
   * suggestions and shows the existente/nueva live indicator. */
  existingVariables?: ExistingVariableOption[];
}) {
  const [popover, setPopover] = useState<PopoverState | null>(null);
  const [varName, setVarName] = useState("");

  const wrapperRef = useRef<HTMLDivElement | null>(null);
  const surfaceRef = useRef<HTMLDivElement | null>(null);

  function handleSurfaceMouseUp() {
    const root = surfaceRef.current;
    if (!root) return;
    const selection = readParagraphSelection(root, window.getSelection());
    if (!selection) {
      // Empty, cross-paragraph or outside selection — dismiss silently.
      setPopover(null);
      return;
    }
    let top = 0;
    let left = 0;
    const wrapper = wrapperRef.current;
    if (selection.rect && wrapper) {
      const wrapperRect = wrapper.getBoundingClientRect();
      top = selection.rect.bottom - wrapperRect.top + 6;
      left = Math.min(
        Math.max(8, selection.rect.left - wrapperRect.left),
        Math.max(8, wrapper.clientWidth - 320),
      );
    }
    // Candidate's surviving occurrences given the existing mappings — the
    // variable name is irrelevant for the interval simulation.
    const candidateEffective =
      countEffectiveOccurrences(structure, [
        ...mappings,
        { text: selection.text, variable: "candidato" },
      ]).get(selection.text) ?? 0;
    setPopover({
      text: selection.text,
      count: countOccurrences(structure, selection.text),
      effectiveCount: candidateEffective,
      top,
      left,
    });
    setVarName(suggestVariableName(selection.text));
  }

  function handleClosePopover() {
    setPopover(null);
    window.getSelection()?.removeAllRanges();
  }

  function handleConfirmMapping() {
    if (!popover) return;
    const result = addMapping(mappings, popover.text, varName);
    if (!result.ok) {
      if (result.reason === "duplicate_text") {
        toast.error("Ese texto ya está convertido en variable.");
      }
      return;
    }
    // Overlap guard: simulate the backend's replacement with the candidate
    // included. A mapping with 0 effective occurrences guarantees a 422
    // missing_texts at submit, so it must never enter the list.
    const effective = countEffectiveOccurrences(structure, result.mappings);
    const candidate = result.mappings[result.mappings.length - 1];
    if ((effective.get(candidate.text) ?? 0) === 0) {
      // Popover already shows the blocked hint for this case; keep the
      // guard for safety (e.g. Enter on a stale popover).
      return;
    }
    const starved = mappings.find((m) => (effective.get(m.text) ?? 0) === 0);
    if (starved) {
      toast.error(
        `No se puede convertir: la variable «${starved.variable}» quedaría ` +
          "sin apariciones porque su texto queda contenido en esta selección.",
      );
      return;
    }
    onMappingsChange(result.mappings);
    handleClosePopover();
  }

  const hasHeaders = structure.headers.length > 0;
  const hasFooters = structure.footers.length > 0;

  return (
    <div className="flex min-w-0 flex-col gap-4">
      {/* Teaching hint — shown until the first mapping exists */}
      {mappings.length === 0 && (
        <div className="flex items-start gap-2.5 rounded-[10px] bg-[var(--bg-accent)] px-3.5 py-2.5 text-[12.5px] leading-[1.45] text-[var(--primary)]">
          <Info className="mt-px size-4 shrink-0" />
          <div className="flex-1">
            Seleccione con el mouse el texto que quiere convertir en
            variable — por ejemplo un nombre, una fecha o un monto — y
            asígnele un nombre. Todas las apariciones exactas se marcarán
            automáticamente.
          </div>
        </div>
      )}

      {/* Document card */}
      <div className="overflow-hidden rounded-xl bg-white shadow-[var(--shadow-md)] ring-1 ring-[rgba(195,198,215,0.30)]">
        <div className="flex items-center justify-between gap-2 border-b border-[rgba(195,198,215,0.20)] bg-[var(--bg-page)] px-6 py-3">
          <div className="flex min-w-0 items-center gap-2 text-[12.5px] text-[var(--fg-3)]">
            <FileText className="size-4 shrink-0 text-[var(--primary)]" />
            <span className="truncate font-medium text-[var(--fg-1)]">
              {file.name}
            </span>
          </div>
          <Badge
            variant="outline"
            className="shrink-0 rounded-full border-[rgba(195,198,215,0.40)] text-[var(--fg-3)]"
          >
            Documento ejemplo
          </Badge>
        </div>

        <div ref={wrapperRef} className="relative">
          <div
            ref={surfaceRef}
            onMouseUp={handleSurfaceMouseUp}
            className="cursor-text select-text px-6 py-5"
            data-testid="example-document-surface"
          >
            {hasHeaders && (
              <ReadOnlySection label="Encabezado">
                {structure.headers.map((node, i) => (
                  <ReadOnlyNode key={`h-${i}`} node={node} mappings={mappings} />
                ))}
              </ReadOnlySection>
            )}

            <ReadOnlySection label="Contenido" emphasis>
              {structure.body.length === 0 ? (
                <p className="text-[12.5px] italic text-[var(--fg-3)]">
                  Este documento no tiene contenido en el cuerpo.
                </p>
              ) : (
                structure.body.map((node, i) => (
                  <ReadOnlyNode key={`b-${i}`} node={node} mappings={mappings} />
                ))
              )}
            </ReadOnlySection>

            {hasFooters && (
              <ReadOnlySection label="Pie de página">
                {structure.footers.map((node, i) => (
                  <ReadOnlyNode key={`f-${i}`} node={node} mappings={mappings} />
                ))}
              </ReadOnlySection>
            )}
          </div>

          {popover && (
            <SelectionPopover
              state={popover}
              varName={varName}
              onVarNameChange={setVarName}
              onConfirm={handleConfirmMapping}
              onClose={handleClosePopover}
              existingVariables={existingVariables}
            />
          )}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Selection popover
// ---------------------------------------------------------------------------

function SelectionPopover({
  state,
  varName,
  onVarNameChange,
  onConfirm,
  onClose,
  existingVariables,
}: {
  state: PopoverState;
  varName: string;
  onVarNameChange: (value: string) => void;
  onConfirm: () => void;
  onClose: () => void;
  existingVariables?: ExistingVariableOption[];
}) {
  const nameIsValid = isValidVariableName(varName);
  const showInvalid = varName.length > 0 && !nameIsValid;
  const crossesFormatting = state.count === 0;
  const consumedByLonger = state.count > 0 && state.effectiveCount === 0;

  const withReuse = (existingVariables?.length ?? 0) > 0;
  const isExisting =
    withReuse && existingVariables!.some((o) => o.name === varName);
  // Narrow by the typed name when it partially matches something; otherwise
  // keep the full list — the panel doubles as a browse surface for reuse
  // (an auto-suggested brand-new name must not hide every option).
  const filtered = withReuse
    ? filterVariableOptions(existingVariables!, varName)
    : [];
  const suggestions =
    withReuse && filtered.length === 0 ? existingVariables! : filtered;

  return (
    <div
      role="dialog"
      aria-label="Convertir en variable"
      data-testid="selection-popover"
      className="absolute z-20 w-[300px] max-w-[calc(100vw-3rem)] rounded-xl bg-white p-3.5 shadow-[var(--shadow-lg)] ring-1 ring-[rgba(195,198,215,0.30)]"
      style={{ top: state.top, left: state.left }}
    >
      <div className="mb-2 flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <div className="truncate font-mono text-[11.5px] font-medium text-[var(--fg-1)]">
            «{truncateText(state.text, 48)}»
          </div>
          <div className="text-[11px] text-[var(--fg-3)]">
            {state.count}{" "}
            {state.count === 1 ? "aparición" : "apariciones"} en el documento
          </div>
        </div>
        <Button
          type="button"
          variant="ghost"
          size="icon-sm"
          aria-label="Cerrar"
          onClick={onClose}
          className="-m-1 size-6 shrink-0 text-[var(--fg-3)]"
        >
          <X className="size-3.5" />
        </Button>
      </div>

      {crossesFormatting ? (
        <p className="m-0 text-[11px] leading-[1.45] text-[#78350f]">
          El texto seleccionado cruza distintos formatos del documento y no
          puede convertirse tal cual. Pruebe con una selección más corta.
        </p>
      ) : consumedByLonger ? (
        <p className="m-0 text-[11px] leading-[1.45] text-[#78350f]">
          Todas las apariciones de este texto ya están dentro de una variable
          marcada más larga, por lo que no quedaría ninguna para reemplazar.
          Quite esa variable o elija otro texto.
        </p>
      ) : (
        <>
          <div className="grid gap-1.5">
            <Label
              htmlFor="from-example-variable-name"
              className="text-xs font-semibold uppercase tracking-[0.04em] text-[var(--fg-3)]"
            >
              Nombre de la variable
            </Label>
            <Input
              id="from-example-variable-name"
              value={varName}
              onChange={(e) => onVarNameChange(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && nameIsValid) {
                  e.preventDefault();
                  onConfirm();
                } else if (e.key === "Escape") {
                  e.preventDefault();
                  onClose();
                }
              }}
              placeholder="nombre_cliente"
              className="font-mono"
              autoFocus
            />
            {/* Live indicator (reuse mode only): does this name reuse a
                shared variable or add a new fill-in step at generation? */}
            {withReuse && nameIsValid && (
              <div>
                {isExisting ? (
                  <span className="inline-flex items-center gap-1 rounded-full bg-[var(--bg-accent)] px-2 py-0.5 text-[10.5px] font-semibold text-[var(--primary)]">
                    <span className="size-1.5 rounded-full bg-[var(--primary)]" />
                    Variable existente — reutiliza el valor compartido
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 rounded-full bg-[#fef3c7] px-2 py-0.5 text-[10.5px] font-semibold text-[#78350f]">
                    <span className="size-1.5 rounded-full bg-[#b45309]" />
                    Variable nueva — se pedirá al generar
                  </span>
                )}
              </div>
            )}
            <p
              className={`m-0 text-[11px] leading-[1.4] ${
                showInvalid
                  ? "text-[var(--destructive)]"
                  : "text-[var(--fg-3)]"
              }`}
            >
              Solo minúsculas, números y guion bajo, sin espacios (ej.
              nombre_cliente).
            </p>
          </div>

          {/* Existing-variable suggestions (reuse mode only) — filtered by
              the typed name; clicking one fills the input. */}
          {withReuse && (
            <div className="mt-2 border-t border-[rgba(195,198,215,0.20)] pt-2">
              <div className="mb-1 text-[11px] font-semibold uppercase tracking-[0.04em] text-[var(--fg-3)]">
                Variables existentes
              </div>
              <ul className="flex max-h-32 flex-col gap-0.5 overflow-y-auto">
                {suggestions.map((option) => (
                  <li key={option.name}>
                    <button
                      type="button"
                      onClick={() => onVarNameChange(option.name)}
                      title={`Usar variable existente ${option.name}`}
                      className="flex w-full items-center justify-between gap-2 rounded-md px-2 py-1 text-left transition-colors hover:bg-[var(--bg-accent)]/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
                    >
                      <span className="truncate font-mono text-[11.5px] font-medium text-[var(--primary)]">
                        {option.name}
                      </span>
                      <span className="shrink-0 text-[10.5px] text-[var(--fg-3)]">
                        {option.source}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <Button
            type="button"
            onClick={onConfirm}
            disabled={!nameIsValid}
            className="mt-2.5 w-full bg-gradient-to-br from-[#004ac6] to-[#2563eb] font-semibold text-white shadow-[var(--shadow-brand-sm)] hover:shadow-[var(--shadow-brand-md)] disabled:opacity-60"
          >
            Convertir en variable
          </Button>
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Read-only structure renderer (highlight-aware, no variable inputs)
// ---------------------------------------------------------------------------

function HighlightedSpans({
  spans,
  mappings,
}: {
  spans: StructureSpan[];
  mappings: VariableMapping[];
}) {
  return (
    <>
      {spans.map((span, spanIdx) => (
        <Fragment key={spanIdx}>
          {segmentText(span.text, mappings).map((segment, segIdx) =>
            segment.mapping ? (
              <mark
                key={segIdx}
                data-variable={segment.mapping.variable}
                title={`{{ ${segment.mapping.variable} }}`}
                className="rounded-[4px] bg-[var(--bg-accent)] px-0.5 font-medium text-[var(--primary)]"
              >
                {segment.text}
              </mark>
            ) : (
              <Fragment key={segIdx}>{segment.text}</Fragment>
            ),
          )}
        </Fragment>
      ))}
    </>
  );
}

function ReadOnlyNode({
  node,
  mappings,
}: {
  node: StructureNode;
  mappings: VariableMapping[];
}) {
  if (node.kind === "table") {
    return <ReadOnlyTable node={node} mappings={mappings} />;
  }
  if (node.kind === "list_bullet" || node.kind === "list_number") {
    return <ReadOnlyListItem node={node} mappings={mappings} />;
  }
  return <ReadOnlyText node={node} mappings={mappings} />;
}

function ReadOnlyText({
  node,
  mappings,
}: {
  node: StructureNode;
  mappings: VariableMapping[];
}) {
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
    <p className={className} data-selectable-paragraph="true">
      <HighlightedSpans spans={node.spans} mappings={mappings} />
    </p>
  );
}

function ReadOnlyListItem({
  node,
  mappings,
}: {
  node: StructureNode;
  mappings: VariableMapping[];
}) {
  const isBullet = node.kind === "list_bullet";
  const indent = Math.max(node.level, 1);
  // Same generic marker rationale as FullDocumentEditor's ListItemNode: the
  // original numbering isn't in the extracted run text.
  const marker = isBullet ? "•" : "1.";
  return (
    <p
      className="my-1 flex gap-2 text-[14px] leading-[1.7] text-[var(--fg-1)]"
      style={{ paddingLeft: `${(indent - 1) * 16 + 12}px` }}
      data-selectable-paragraph="true"
    >
      <span
        className={`shrink-0 select-none ${isBullet ? "w-3 text-[var(--fg-3)]" : "w-5 font-medium tabular-nums text-[var(--fg-3)]"}`}
      >
        {marker}
      </span>
      <span className="flex-1">
        <HighlightedSpans spans={node.spans} mappings={mappings} />
      </span>
    </p>
  );
}

function ReadOnlyTable({
  node,
  mappings,
}: {
  node: StructureNode;
  mappings: VariableMapping[];
}) {
  return (
    <div className="my-3 overflow-x-auto">
      <table className="w-full border-collapse text-[13px]">
        <tbody>
          {node.rows.map((row, rowIdx) => (
            <tr
              key={rowIdx}
              className="border-b border-[rgba(195,198,215,0.30)] last:border-b-0"
            >
              {row.cells.map((cell: StructureTableCell, cellIdx) => (
                <td
                  key={cellIdx}
                  className="border-l border-[rgba(195,198,215,0.20)] px-2.5 py-1.5 align-top first:border-l-0"
                >
                  {cell.nodes.length === 0 ? (
                    <span className="text-[var(--fg-3)]">—</span>
                  ) : (
                    cell.nodes.map((child, childIdx) => (
                      <ReadOnlyNode
                        key={childIdx}
                        node={child}
                        mappings={mappings}
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

function ReadOnlySection({
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
      <div className="sd-meta mb-2 inline-block select-none rounded bg-[var(--bg-page)] px-2 py-0.5">
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
