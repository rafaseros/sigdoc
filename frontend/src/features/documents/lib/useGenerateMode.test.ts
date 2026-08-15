import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { act, renderHook } from "@testing-library/react";

import { GENERATE_MODE_STORAGE_KEY, useGenerateMode } from "./useGenerateMode";

beforeEach(() => {
  window.localStorage.clear();
});

afterEach(() => {
  window.localStorage.clear();
});

describe("useGenerateMode", () => {
  it("defaults to 'full' when localStorage is empty", () => {
    const { result } = renderHook(() => useGenerateMode());
    expect(result.current[0]).toBe("full");
  });

  it("reads a previously saved value", () => {
    window.localStorage.setItem(GENERATE_MODE_STORAGE_KEY, "form");
    const { result } = renderHook(() => useGenerateMode());
    expect(result.current[0]).toBe("form");
  });

  it("reads a previously saved 'fields' value", () => {
    window.localStorage.setItem(GENERATE_MODE_STORAGE_KEY, "fields");
    const { result } = renderHook(() => useGenerateMode());
    expect(result.current[0]).toBe("fields");
  });

  it("persists the choice to localStorage when setMode is called", () => {
    const { result } = renderHook(() => useGenerateMode());

    act(() => {
      result.current[1]("form");
    });

    expect(result.current[0]).toBe("form");
    expect(window.localStorage.getItem(GENERATE_MODE_STORAGE_KEY)).toBe("form");
  });

  it("persists the 'fields' choice to localStorage", () => {
    const { result } = renderHook(() => useGenerateMode());

    act(() => {
      result.current[1]("fields");
    });

    expect(result.current[0]).toBe("fields");
    expect(window.localStorage.getItem(GENERATE_MODE_STORAGE_KEY)).toBe(
      "fields",
    );
  });

  it("falls back to 'full' when the stored value is invalid", () => {
    window.localStorage.setItem(GENERATE_MODE_STORAGE_KEY, "not-a-mode");
    const { result } = renderHook(() => useGenerateMode());
    expect(result.current[0]).toBe("full");
  });
});
