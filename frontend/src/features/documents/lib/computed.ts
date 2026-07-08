import type { ComputedOperator } from "@/features/templates/api/queries";

/**
 * Strict numeric-source pattern mirroring the backend's `Decimal(text)`
 * parsing semantics (see `_parse_decimal` in
 * `backend/src/app/domain/services/computed_variables.py`): only a plain
 * "-123" / "123.45" style string (after trim) is accepted. Locale-formatted
 * numbers ("1.500,50") or trailing garbage ("12abc") are rejected — lenient
 * `parseFloat` would otherwise truncate-parse these into a plausible-looking
 * number the server would never accept, showing a live pill value while the
 * actual document would render blank (server resolves unparseable sources to
 * "").
 */
const STRICT_DECIMAL_PATTERN = /^-?\d+(\.\d+)?$/;

function parseStrictDecimal(raw: string): number | null {
  const trimmed = raw.trim();
  if (!STRICT_DECIMAL_PATTERN.test(trimmed)) return null;
  const n = Number(trimmed);
  return Number.isFinite(n) ? n : null;
}

/**
 * Half-up rounding to 2 decimals, matching the server's `Decimal.quantize(
 * Decimal("0.01"), rounding=ROUND_HALF_UP)`. Plain `toFixed(2)` uses the
 * IEEE-754 double's nearest representable value, which rounds some exact
 * ".005" boundaries DOWN (e.g. `1.005.toFixed(2)` === "1.00", not "1.01").
 * Nudging by `Number.EPSILON` before rounding at the integer-cents level
 * corrects those boundary cases to match ROUND_HALF_UP.
 */
function roundHalfUp2(value: number): string {
  const cents = Math.round((value + Number.EPSILON) * 100) / 100;
  return cents.toFixed(2);
}

/**
 * Live, client-side preview of a formula-computed variable's pill.
 *
 * The server is the source of truth on generate/preview (ROUND_HALF_UP,
 * 2-decimal string) — this only drives the inline pill so the user sees a
 * plausible result while typing into the source variable. Non-finite
 * results (non-numeric source, division by zero) render as "—" instead of
 * NaN/Infinity.
 */
export function computeFormulaValue(
  sourceValue: string,
  operator: ComputedOperator,
  operand: number,
): string {
  const n = parseStrictDecimal(sourceValue);
  if (n === null) return "—";

  let result: number;
  switch (operator) {
    case "+":
      result = n + operand;
      break;
    case "-":
      result = n - operand;
      break;
    case "*":
      result = n * operand;
      break;
    case "/":
      result = operand !== 0 ? n / operand : NaN;
      break;
  }

  if (!Number.isFinite(result)) return "—";
  return roundHalfUp2(result);
}
