/**
 * fromExample.ts
 *
 * Pure helpers for the "create template from example document" flow:
 * variable-name validation/suggestion, selection normalization, occurrence
 * counting across the whole document structure, mapping add/duplicate rules,
 * highlight segmentation, and backend 422/409 error-detail parsing.
 *
 * Selection math is isolated here (readParagraphSelection) so it can be
 * tested against fabricated Selection objects — jsdom's window.getSelection
 * is too limited to drive from component tests.
 */

import type { StructureNode, TemplateStructure } from "../api/queries";

export interface VariableMapping {
  /** Exact literal text as it appears in the document (already trimmed). */
  text: string;
  /** Target variable name (snake_case, backend rule ^[a-z_][a-z0-9_]*$). */
  variable: string;
}

// ---------------------------------------------------------------------------
// Variable names
// ---------------------------------------------------------------------------

/** Mirror of the backend rule for mapping variable names. */
export const VARIABLE_NAME_PATTERN = /^[a-z_][a-z0-9_]*$/;

export function isValidVariableName(name: string): boolean {
  return VARIABLE_NAME_PATTERN.test(name);
}

const MAX_SUGGESTED_NAME_LENGTH = 50;

/**
 * Suggest a snake_case ascii variable name from the selected literal text.
 * Returns "" when nothing usable remains (caller keeps the input empty).
 */
export function suggestVariableName(text: string): string {
  const normalized = text
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "") // strip combining diacritics (é → e, ñ → n)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, MAX_SUGGESTED_NAME_LENGTH)
    .replace(/_+$/g, "");
  if (!normalized) return "";
  return /^[0-9]/.test(normalized) ? `var_${normalized}` : normalized;
}

// ---------------------------------------------------------------------------
// Selection text
// ---------------------------------------------------------------------------

/**
 * Normalize a raw mouse selection into the effective mapping text: trim
 * leading/trailing whitespace only — internal spacing must stay exact
 * because the backend matches the literal text case- and space-sensitively.
 */
export function normalizeSelectionText(raw: string): string {
  return raw.trim();
}

// ---------------------------------------------------------------------------
// Occurrence counting
// ---------------------------------------------------------------------------

/** Non-overlapping, case-sensitive occurrence count of needle in haystack. */
export function countOccurrencesInText(
  haystack: string,
  needle: string,
): number {
  if (!needle) return 0;
  let count = 0;
  let idx = haystack.indexOf(needle);
  while (idx !== -1) {
    count++;
    idx = haystack.indexOf(needle, idx + needle.length);
  }
  return count;
}

function countInNode(node: StructureNode, text: string): number {
  let count = 0;
  for (const span of node.spans) {
    count += countOccurrencesInText(span.text, text);
  }
  for (const row of node.rows) {
    for (const cell of row.cells) {
      for (const child of cell.nodes) {
        count += countInNode(child, text);
      }
    }
  }
  return count;
}

/**
 * Count exact occurrences of `text` across the whole structure — headers,
 * body and footers, including nodes nested inside table cells. Matching is
 * per-span (text crossing a span boundary is never counted, mirroring what
 * the backend can actually replace).
 */
export function countOccurrences(
  structure: TemplateStructure,
  text: string,
): number {
  if (!text) return 0;
  const sections = [structure.headers, structure.body, structure.footers];
  let count = 0;
  for (const section of sections) {
    for (const node of section) {
      count += countInNode(node, text);
    }
  }
  return count;
}

// ---------------------------------------------------------------------------
// Effective occurrences (backend replacement simulation)
// ---------------------------------------------------------------------------

function collectBlobs(node: StructureNode, out: string[]): void {
  for (const span of node.spans) {
    out.push(span.text);
  }
  for (const row of node.rows) {
    for (const cell of row.cells) {
      for (const child of cell.nodes) {
        collectBlobs(child, out);
      }
    }
  }
}

/** First index of `needle` whose span overlaps no consumed interval. */
function findUnconsumed(
  haystack: string,
  needle: string,
  consumed: Array<[number, number]>,
): number {
  let idx = haystack.indexOf(needle);
  while (idx !== -1) {
    const end = idx + needle.length;
    if (!consumed.some(([s, e]) => s < end && idx < e)) return idx;
    idx = haystack.indexOf(needle, idx + 1);
  }
  return -1;
}

/**
 * Simulate the backend's mapping application to count how many occurrences
 * of each mapping's text actually SURVIVE: mappings are processed
 * longest-text-first (ties keep input order — same stable sort as the
 * backend), each match consumes its interval, and later (shorter) mappings
 * can never match inside a consumed interval. A mapping whose every raw
 * occurrence is consumed would fail the submit with 422 missing_texts, so
 * the UI must treat an effective count of 0 as invalid.
 *
 * Blob traversal mirrors countOccurrences: headers/body/footers spans plus
 * recursive table cells, matching per span. Returns a map keyed by each
 * mapping's text (texts are unique — duplicates are rejected by addMapping).
 */
export function countEffectiveOccurrences(
  structure: TemplateStructure,
  mappings: VariableMapping[],
): Map<string, number> {
  const counts = new Map<string, number>();
  for (const m of mappings) {
    counts.set(m.text, counts.get(m.text) ?? 0);
  }
  const usable = mappings.filter((m) => m.text.length > 0);
  if (usable.length === 0) return counts;

  // Longest-text-first, stable on ties — mirrors _validate_mappings.
  const ordered = [...usable].sort((a, b) => b.text.length - a.text.length);

  const blobs: string[] = [];
  for (const section of [structure.headers, structure.body, structure.footers]) {
    for (const node of section) {
      collectBlobs(node, blobs);
    }
  }

  for (const blob of blobs) {
    // Fresh interval set per blob — the backend protects per paragraph.
    const consumed: Array<[number, number]> = [];
    for (const mapping of ordered) {
      const needle = mapping.text;
      let idx = findUnconsumed(blob, needle, consumed);
      while (idx !== -1) {
        consumed.push([idx, idx + needle.length]);
        counts.set(mapping.text, (counts.get(mapping.text) ?? 0) + 1);
        idx = findUnconsumed(blob, needle, consumed);
      }
    }
  }
  return counts;
}

// ---------------------------------------------------------------------------
// Mapping list rules
// ---------------------------------------------------------------------------

export type AddMappingResult =
  | { ok: true; mappings: VariableMapping[] }
  | { ok: false; reason: "empty_text" | "invalid_variable" | "duplicate_text" };

/**
 * Add a mapping to the list, enforcing the flow's rules: non-empty trimmed
 * text, valid variable name, and no duplicate exact text (the backend
 * rejects duplicate texts; the same variable for two different texts is
 * allowed). Never mutates the input list.
 */
export function addMapping(
  mappings: VariableMapping[],
  rawText: string,
  variable: string,
): AddMappingResult {
  const text = normalizeSelectionText(rawText);
  if (!text) return { ok: false, reason: "empty_text" };
  if (!isValidVariableName(variable)) {
    return { ok: false, reason: "invalid_variable" };
  }
  if (mappings.some((m) => m.text === text)) {
    return { ok: false, reason: "duplicate_text" };
  }
  return { ok: true, mappings: [...mappings, { text, variable }] };
}

// ---------------------------------------------------------------------------
// Existing-variable reuse (attach-related-file-from-example flow)
// ---------------------------------------------------------------------------

/** Fixed source label for variables not contributed by a related file. */
export const PRIMARY_SOURCE_LABEL = "Documento principal";

export interface ExistingVariableOption {
  name: string;
  /** Source hint: a related file's label, or PRIMARY_SOURCE_LABEL. */
  source: string;
}

/**
 * Build the reusable-variable options for the attach-from-example popover
 * from a version's variable union plus its related files. Union order is
 * preserved. Source annotation is intentionally cheap: the FIRST related
 * file whose per-file set contains the name wins; names in no related file
 * are attributed to the primary document. (A name present in both the
 * primary and a file shows the file label — the annotation is a discovery
 * hint, not an authoritative provenance record.)
 */
export function buildExistingVariableOptions(
  versionVariables: string[],
  files: Array<{ label: string; variables: string[] }>,
): ExistingVariableOption[] {
  return versionVariables.map((name) => {
    const file = files.find((f) => f.variables.includes(name));
    return { name, source: file ? file.label : PRIMARY_SOURCE_LABEL };
  });
}

/**
 * Case-insensitive containment filter over the reuse options by the typed
 * variable name. A blank query keeps every option (the list doubles as a
 * browse surface before the user types anything).
 */
export function filterVariableOptions(
  options: ExistingVariableOption[],
  query: string,
): ExistingVariableOption[] {
  const needle = query.trim().toLowerCase();
  if (!needle) return options;
  return options.filter((o) => o.name.toLowerCase().includes(needle));
}

/**
 * Distinct mapping variable names NOT present in `existingVariables`, in
 * first-appearance order. Each of these becomes an extra fill-in step at
 * generation time, so the UI surfaces them explicitly ("variable nueva").
 */
export function newVariableNames(
  mappings: VariableMapping[],
  existingVariables: string[],
): string[] {
  const existing = new Set(existingVariables);
  const result: string[] = [];
  for (const mapping of mappings) {
    if (!existing.has(mapping.variable) && !result.includes(mapping.variable)) {
      result.push(mapping.variable);
    }
  }
  return result;
}

// ---------------------------------------------------------------------------
// Highlight segmentation
// ---------------------------------------------------------------------------

export interface TextSegment {
  text: string;
  /** The mapping this segment belongs to, or null for plain text. */
  mapping: VariableMapping | null;
}

/**
 * Split a span's text into plain/highlighted segments for rendering.
 * Left-to-right scan: at each position the earliest match wins; on a tie at
 * the same position, the longest mapping text wins. Occurrences that fall
 * inside an already-consumed longer match are simply not re-highlighted
 * (visual overlap is out of scope by design).
 */
export function segmentText(
  text: string,
  mappings: VariableMapping[],
): TextSegment[] {
  if (!text) return [];
  const usable = mappings.filter((m) => m.text.length > 0);
  if (usable.length === 0) return [{ text, mapping: null }];

  const segments: TextSegment[] = [];
  let cursor = 0;

  while (cursor < text.length) {
    let bestIdx = -1;
    let bestMapping: VariableMapping | null = null;
    for (const mapping of usable) {
      const idx = text.indexOf(mapping.text, cursor);
      if (idx === -1) continue;
      if (
        bestIdx === -1 ||
        idx < bestIdx ||
        (idx === bestIdx && mapping.text.length > bestMapping!.text.length)
      ) {
        bestIdx = idx;
        bestMapping = mapping;
      }
    }
    if (bestIdx === -1 || !bestMapping) {
      segments.push({ text: text.slice(cursor), mapping: null });
      break;
    }
    if (bestIdx > cursor) {
      segments.push({ text: text.slice(cursor, bestIdx), mapping: null });
    }
    segments.push({ text: bestMapping.text, mapping: bestMapping });
    cursor = bestIdx + bestMapping.text.length;
  }

  return segments;
}

// ---------------------------------------------------------------------------
// Backend error-detail parsing (POST /templates/from-example)
// ---------------------------------------------------------------------------

export interface FromExampleError {
  message: string;
  /** Detail rows: schema errors[] or missing_texts[], empty otherwise. */
  items: string[];
}

/**
 * Normalize the `detail` payload of a from-example error response. Handles
 * the three backend variants — plain string (409/engine-level 422/400),
 * {message, errors[]} (schema-invalid mappings) and {message,
 * missing_texts[]} (texts not found) — falling back to `fallback` for
 * anything unrecognized.
 */
export function parseFromExampleError(
  detail: unknown,
  fallback: string,
): FromExampleError {
  if (typeof detail === "string" && detail) {
    return { message: detail, items: [] };
  }
  if (detail && typeof detail === "object") {
    const obj = detail as Record<string, unknown>;
    const message = typeof obj.message === "string" ? obj.message : fallback;
    const rawItems = Array.isArray(obj.errors)
      ? obj.errors
      : Array.isArray(obj.missing_texts)
        ? obj.missing_texts
        : [];
    const items = rawItems.filter((i): i is string => typeof i === "string");
    if (message !== fallback || items.length > 0) {
      return { message, items };
    }
  }
  return { message: fallback, items: [] };
}

// ---------------------------------------------------------------------------
// Selection reading (DOM)
// ---------------------------------------------------------------------------

/** Marker attribute set by the read-only renderer on every selectable <p>. */
export const SELECTABLE_PARAGRAPH_ATTR = "data-selectable-paragraph";

export interface ParagraphSelection {
  /** Trimmed selected text. */
  text: string;
  /** Bounding rect of the selection range, for popover anchoring. */
  rect: DOMRect | null;
}

function closestParagraph(node: Node | null): HTMLElement | null {
  if (!node) return null;
  const el =
    node.nodeType === Node.ELEMENT_NODE
      ? (node as HTMLElement)
      : node.parentElement;
  return el?.closest(`[${SELECTABLE_PARAGRAPH_ATTR}]`) ?? null;
}

/**
 * Validate the current selection for the mark-variables flow: it must be
 * non-collapsed, fully inside ONE selectable paragraph, and that paragraph
 * must live under `root`. Returns the trimmed text plus the range rect, or
 * null for anything invalid (caller dismisses silently).
 */
export function readParagraphSelection(
  root: HTMLElement,
  selection: Selection | null,
): ParagraphSelection | null {
  if (!selection || selection.isCollapsed || selection.rangeCount === 0) {
    return null;
  }
  const anchorParagraph = closestParagraph(selection.anchorNode);
  const focusParagraph = closestParagraph(selection.focusNode);
  if (
    !anchorParagraph ||
    anchorParagraph !== focusParagraph ||
    !root.contains(anchorParagraph)
  ) {
    return null;
  }
  const text = normalizeSelectionText(selection.toString());
  if (!text) return null;

  let rect: DOMRect | null = null;
  try {
    rect = selection.getRangeAt(0).getBoundingClientRect();
  } catch {
    rect = null;
  }
  return { text, rect };
}
