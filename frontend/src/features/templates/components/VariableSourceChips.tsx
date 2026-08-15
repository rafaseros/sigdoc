import type { TemplateVersionFile } from "@/features/templates/api/queries";

interface VariableSourceChipsProps {
  variableName: string;
  /** The version's related files. Each file's own `variables` list is the
   * source of truth for which related documents also use `variableName`. */
  files: TemplateVersionFile[];
}

/**
 * Compact provenance line for a single variable: shows which RELATED documents
 * (beyond the primary one) also use it. `variables_meta` is the union across
 * the primary document and every related file, so a variable's provenance is
 * derivable from each file's own `variables` list.
 *
 * Renders `null` when no related file uses the variable (it is implicitly
 * primary-only). The visible line stays short — a muted "También en:" prefix
 * followed by each file's label as a compact chip. The fuller explanation
 * lives only in the group `title` tooltip, never inline.
 */
export function VariableSourceChips({
  variableName,
  files,
}: VariableSourceChipsProps) {
  const usedByFiles = files.filter((f) => f.variables.includes(variableName));
  if (usedByFiles.length === 0) return null;

  const tooltip =
    usedByFiles.length === 1
      ? "Esta variable también aparece en este documento relacionado"
      : "Esta variable también aparece en estos documentos relacionados";

  return (
    <div
      title={tooltip}
      className="flex flex-wrap items-center gap-1 text-[11px] text-[var(--fg-3)]"
    >
      <span>También en:</span>
      {usedByFiles.map((f) => (
        <span
          key={f.id}
          className="var-chip var-chip-muted !font-sans !text-[10px]"
        >
          {f.label}
        </span>
      ))}
    </div>
  );
}
