import "@testing-library/jest-dom/vitest";

// jsdom does not implement layout, so `Element.prototype.scrollIntoView` is
// left unimplemented and logs a noisy "not implemented" error whenever the
// inline document editors call it (e.g. auto-advance bringing the next
// pill's control into view). Stub it out for tests.
Element.prototype.scrollIntoView = () => {};

// Base UI's Select uses floating-ui under the hood, which relies on
// ResizeObserver to keep the popup positioned. jsdom has no layout engine
// and doesn't implement it — stub a no-op so the component doesn't throw.
if (typeof globalThis.ResizeObserver === "undefined") {
  globalThis.ResizeObserver = class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
}
