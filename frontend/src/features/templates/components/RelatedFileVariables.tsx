import { useMemo, useState } from "react";
import { Calculator, Variable } from "lucide-react";

import type {
  TemplateVersionFile,
  VariableMeta,
} from "@/features/templates/api/queries";

interface RelatedFileVariablesProps {
  /** The related file whose variable names should be shown. */
  file: TemplateVersionFile;
  /** The version's variable metadata (the union across the primary document
   * and every related file). Used to tell which of this file's variables are
   * computed so they can be styled/marked like elsewhere in the app. */
  variablesMeta: VariableMeta[];
}

/**
 * Read-only, expandable view of a related file's variables, shown under each
 * related-file row in the Versions tab. Renders every variable name as a chip:
 * plain variables use `.var-chip`/`.var-chip-muted`, and variables that are
 * `computed` (per the matching `variables_meta` entry) use `.var-chip-computed`
 * and carry a small "auto" marker — mirroring how computed variables are
 * surfaced in the Variables tab. Pure/presentational; owns only its open state.
 */
export function RelatedFileVariables({
  file,
  variablesMeta,
}: RelatedFileVariablesProps) {
  const [open, setOpen] = useState(false);
  const count = file.variables.length;

  // Names of the version's computed variables (server-owned, auto-calculated).
  // A `Set` keeps the per-chip lookup below O(1). Derived from the same
  // `variables_meta` union that drives the Variables tab, so this read-only
  // view stays consistent with it.
  const computedNames = useMemo(
    () =>
      new Set(
        variablesMeta.filter((m) => m.computed != null).map((m) => m.name),
      ),
    [variablesMeta],
  );

  // An empty related file has nothing to expand — show a short line instead of
  // an inert toggle.
  if (count === 0) {
    return (
      <span className="text-[11.5px] text-[var(--fg-3)]">Sin variables</span>
    );
  }

  return (
    <div className="flex min-w-0 flex-col gap-1.5">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="inline-flex w-fit items-center gap-1 text-[11.5px] font-medium text-[var(--fg-3)] transition-colors hover:text-[var(--primary)]"
      >
        <Variable className="size-3 shrink-0" />
        {open ? "Ocultar variables" : "Ver variables"} ({count})
      </button>

      {open && (
        <div className="flex flex-wrap gap-1">
          {file.variables.map((name) => {
            const isComputed = computedNames.has(name);
            return (
              <span
                key={name}
                className={`var-chip ${
                  isComputed ? "var-chip-computed" : "var-chip-muted"
                }`}
                title={
                  isComputed
                    ? `${name} · calculada automáticamente`
                    : name
                }
              >
                {name}
                {isComputed && (
                  <span
                    className="ml-1 inline-flex items-center gap-0.5 text-[9px] font-semibold uppercase tracking-wide"
                    aria-label="calculada automáticamente"
                  >
                    <Calculator className="size-2.5 shrink-0" />
                    auto
                  </span>
                )}
              </span>
            );
          })}
        </div>
      )}
    </div>
  );
}
