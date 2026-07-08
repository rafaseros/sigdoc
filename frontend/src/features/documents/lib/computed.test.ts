import { describe, expect, it } from "vitest";
import { computeFormulaValue } from "./computed";

describe("computeFormulaValue", () => {
  it("adds the operand to a numeric source value", () => {
    expect(computeFormulaValue("100", "+", 50)).toBe("150.00");
  });

  it("subtracts the operand from a numeric source value", () => {
    expect(computeFormulaValue("100", "-", 25)).toBe("75.00");
  });

  it("multiplies the source value by the operand", () => {
    expect(computeFormulaValue("10", "*", 1.21)).toBe("12.10");
  });

  it("divides the source value by the operand", () => {
    expect(computeFormulaValue("100", "/", 4)).toBe("25.00");
  });

  it("returns an em dash when the source value is not numeric", () => {
    expect(computeFormulaValue("", "+", 10)).toBe("—");
    expect(computeFormulaValue("not-a-number", "+", 10)).toBe("—");
  });

  it("returns an em dash when dividing by an operand of 0", () => {
    expect(computeFormulaValue("100", "/", 0)).toBe("—");
  });

  it("formats decimals to exactly 2 places", () => {
    expect(computeFormulaValue("10.005", "+", 0)).toBe("10.01");
  });

  // ── Strict source parsing (mirrors the backend's Decimal(text) parsing) ──

  it("returns an em dash for a locale-formatted (thousands/comma-decimal) source", () => {
    expect(computeFormulaValue("1.500,50", "+", 10)).toBe("—");
  });

  it("returns an em dash for a source with trailing garbage instead of truncate-parsing it", () => {
    expect(computeFormulaValue("12abc", "+", 10)).toBe("—");
  });

  it("still computes normally for a plain decimal source", () => {
    expect(computeFormulaValue("1500.50", "+", 10)).toBe("1510.50");
  });

  // ── Half-up rounding (mirrors the server's ROUND_HALF_UP) ────────────────

  it("rounds 1.005 half-up to 1.01", () => {
    expect(computeFormulaValue("1.005", "+", 0)).toBe("1.01");
  });

  it("rounds 2.675 half-up to 2.68", () => {
    expect(computeFormulaValue("2.675", "+", 0)).toBe("2.68");
  });

  it("rounds 100.005 half-up to 100.01", () => {
    expect(computeFormulaValue("100.005", "+", 0)).toBe("100.01");
  });

  it("rounds 0.125 half-up to 0.13", () => {
    expect(computeFormulaValue("0.125", "+", 0)).toBe("0.13");
  });
});
