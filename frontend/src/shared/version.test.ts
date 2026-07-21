import { describe, expect, it } from "vitest";

import { APP_VERSION, CHANGELOG } from "./version";

describe("version module", () => {
  it("exposes a full semver APP_VERSION", () => {
    expect(APP_VERSION).toMatch(/^\d+\.\d+\.\d+$/);
  });

  it("keeps the newest changelog entry in sync with APP_VERSION", () => {
    expect(CHANGELOG.length).toBeGreaterThan(0);
    // Entries use the short `major.minor` form (rendered as `v4.0` chips).
    expect(APP_VERSION.startsWith(`${CHANGELOG[0].version}.`)).toBe(true);
  });

  it("orders entries newest first", () => {
    const majors = CHANGELOG.map((entry) => Number.parseInt(entry.version, 10));
    const sortedDescending = [...majors].sort((a, b) => b - a);
    expect(majors).toEqual(sortedDescending);
  });

  it("has unique, well-formed entries with concise item lists", () => {
    const versions = CHANGELOG.map((entry) => entry.version);
    expect(new Set(versions).size).toBe(versions.length);

    for (const entry of CHANGELOG) {
      expect(entry.version).toMatch(/^\d+\.\d+$/);
      expect(entry.title.trim().length).toBeGreaterThan(0);
      expect(entry.items.length).toBeGreaterThanOrEqual(3);
      expect(entry.items.length).toBeLessThanOrEqual(6);
      for (const item of entry.items) {
        expect(item.trim().length).toBeGreaterThan(0);
      }
    }
  });
});
