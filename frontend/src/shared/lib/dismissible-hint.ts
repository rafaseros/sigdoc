/**
 * Dismissible hint persistence — see STYLE_GUIDE.md §16.
 *
 * A "hint" is a compact, dismissible teaching banner (guide §9 compact info
 * recipe) shown once to point the user at an underused feature. Dismissal is
 * remembered per browser via `localStorage` under the key
 * `hint:<name>:dismissed`.
 *
 * Guarded try/catch, same pattern as `TemplateList.tsx`'s view-mode
 * persistence: `localStorage` can be unavailable (private browsing, disabled
 * storage) — in that case the hint simply re-appears every render, which is
 * a safe degradation.
 */

function storageKey(name: string): string {
  return `hint:${name}:dismissed`;
}

export function isHintDismissed(name: string): boolean {
  if (typeof window === "undefined") return false;
  try {
    return window.localStorage.getItem(storageKey(name)) === "1";
  } catch {
    return false;
  }
}

export function dismissHint(name: string): void {
  try {
    window.localStorage.setItem(storageKey(name), "1");
  } catch {
    // localStorage unavailable — dismissal only holds for this render/session.
  }
}
