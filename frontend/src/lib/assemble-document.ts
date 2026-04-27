/**
 * assemble-document.ts
 *
 * Pure helper that converts a flat `VariableMeta[]` array into an ordered,
 * deduplicated list of `DocumentParagraph`s ready for inline editing.
 *
 * No React, no side-effects — 100% pure and easily unit-testable.
 */

export interface VariableMeta {
  name: string;
  contexts: string[];
}

export interface DocumentSegment {
  type: "text" | "placeholder";
  /** For type "text": the literal string. For type "placeholder": the variable name. */
  content: string;
}

export interface DocumentParagraph {
  /** Stable ID derived from a simple hash of the raw paragraph text. */
  id: string;
  segments: DocumentSegment[];
  /** Unique variable names that appear in this paragraph. */
  variableNames: string[];
}

/** Cheap, stable, non-cryptographic hash for paragraph dedup IDs. */
function hashString(s: string): string {
  let h = 0;
  for (let i = 0; i < s.length; i++) {
    h = (Math.imul(31, h) + s.charCodeAt(i)) | 0;
  }
  return `p${(h >>> 0).toString(36)}`;
}

/** Split a paragraph string into text + placeholder segments. */
function parseSegments(paragraph: string): DocumentSegment[] {
  const pattern = /\{\{\s*(\w+)\s*\}\}/g;
  const segments: DocumentSegment[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = pattern.exec(paragraph)) !== null) {
    if (match.index > lastIndex) {
      segments.push({ type: "text", content: paragraph.slice(lastIndex, match.index) });
    }
    segments.push({ type: "placeholder", content: match[1] });
    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < paragraph.length) {
    segments.push({ type: "text", content: paragraph.slice(lastIndex) });
  }

  if (segments.length === 0) {
    segments.push({ type: "text", content: paragraph });
  }

  return segments;
}

/**
 * Assemble a deduplicated, document-ordered list of paragraphs from
 * `variablesMeta`.
 *
 * Ordering heuristic: paragraphs appear in the order their first variable
 * appears in the `variablesMeta` array. This mirrors the backend's
 * extraction order, which follows document reading order.
 *
 * Variables with no context paragraphs are appended as a synthetic
 * "Otros datos" paragraph at the end so no field is ever lost.
 */
export function assembleDocument(variablesMeta: VariableMeta[]): DocumentParagraph[] {
  // Map: raw paragraph text → first-seen insertion index (for ordering)
  const paragraphOrder = new Map<string, number>();
  let insertionCounter = 0;

  for (const meta of variablesMeta) {
    for (const ctx of meta.contexts) {
      if (!paragraphOrder.has(ctx)) {
        paragraphOrder.set(ctx, insertionCounter++);
      }
    }
  }

  // Collect all unique paragraph texts, sorted by insertion order
  const orderedTexts = [...paragraphOrder.entries()]
    .sort((a, b) => a[1] - b[1])
    .map(([text]) => text);

  // Build the paragraph objects
  const paragraphs: DocumentParagraph[] = orderedTexts.map((text) => {
    const segments = parseSegments(text);
    const variableNames = segments
      .filter((s) => s.type === "placeholder")
      .map((s) => s.content)
      // Dedupe while preserving order
      .filter((v, i, arr) => arr.indexOf(v) === i);
    return { id: hashString(text), segments, variableNames };
  });

  // Append a fallback "Otros datos" paragraph for variables with no context
  const coveredVars = new Set(paragraphs.flatMap((p) => p.variableNames));
  const orphanVars = variablesMeta
    .map((m) => m.name)
    .filter((name) => !coveredVars.has(name));

  if (orphanVars.length > 0) {
    // One paragraph per orphan variable so each gets its own widget
    for (const name of orphanVars) {
      const syntheticText = `Otros datos: {{${name}}}`;
      paragraphs.push({
        id: hashString(syntheticText),
        segments: [
          { type: "text", content: "Otros datos: " },
          { type: "placeholder", content: name },
        ],
        variableNames: [name],
      });
    }
  }

  return paragraphs;
}
