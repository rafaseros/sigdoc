/**
 * useGenerateMode — remembers how the user prefers to load data on the
 * single-document generate screen. Three levels, most → least document context:
 *
 * - "full"   → FullDocumentEditor (full document view with inline pills).
 * - "form"   → guided flat form (each field shown with its document context).
 * - "fields" → quick flat form (each field shown with only its help text).
 *
 * The choice is persisted per browser under `sigdoc:generate-mode`, so it
 * survives reloads and version switches. localStorage access is guarded
 * (private browsing / disabled storage): on failure the mode still works
 * in-memory for the session, it just won't persist. This is a Vite SPA with
 * no SSR, but the `typeof window` guard mirrors the rest of the codebase.
 */

import { useCallback, useState } from "react";

export type GenerateMode = "full" | "form" | "fields";

export const GENERATE_MODE_STORAGE_KEY = "sigdoc:generate-mode";

function readStoredMode(): GenerateMode {
  if (typeof window === "undefined") return "full";
  try {
    const raw = window.localStorage.getItem(GENERATE_MODE_STORAGE_KEY);
    return raw === "full" || raw === "form" || raw === "fields" ? raw : "full";
  } catch {
    // localStorage unavailable — fall back to the default for this session.
    return "full";
  }
}

export function useGenerateMode(): [GenerateMode, (mode: GenerateMode) => void] {
  const [mode, setModeState] = useState<GenerateMode>(readStoredMode);

  const setMode = useCallback((next: GenerateMode) => {
    setModeState(next);
    try {
      window.localStorage.setItem(GENERATE_MODE_STORAGE_KEY, next);
    } catch {
      // localStorage unavailable — the choice holds only for this session.
    }
  }, []);

  return [mode, setMode];
}
