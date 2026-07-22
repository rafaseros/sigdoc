import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { ChangePasswordDialog } from "./ChangePasswordDialog";
import { apiClient } from "@/shared/lib/api-client";

vi.mock("@/shared/lib/api-client", () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}));

const toastSuccess = vi.fn();
const toastError = vi.fn();

vi.mock("sonner", () => ({
  toast: {
    success: (...args: unknown[]) => toastSuccess(...args),
    error: (...args: unknown[]) => toastError(...args),
  },
}));

function renderDialog() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  render(
    <QueryClientProvider client={queryClient}>
      <ChangePasswordDialog open onOpenChange={vi.fn()} />
    </QueryClientProvider>,
  );
}

function fillAndSubmit() {
  // fireEvent.change sets each field instantly (no per-keystroke cost), which
  // keeps this three-field form fast and deterministic under full-suite load.
  fireEvent.change(screen.getByLabelText(/contraseña actual/i), {
    target: { value: "oldpass" },
  });
  fireEvent.change(screen.getByLabelText(/^nueva contraseña/i), {
    target: { value: "newpass123" },
  });
  fireEvent.change(screen.getByLabelText(/confirmar nueva contraseña/i), {
    target: { value: "newpass123" },
  });
  fireEvent.click(screen.getByRole("button", { name: /actualizar/i }));
}

describe("ChangePasswordDialog — error handling", () => {
  beforeEach(() => {
    vi.mocked(apiClient.post).mockReset();
    toastSuccess.mockReset();
    toastError.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("surfaces the backend Spanish detail instead of the raw axios message", async () => {
    vi.mocked(apiClient.post).mockRejectedValue({
      message: "Request failed with status code 400",
      response: {
        status: 400,
        data: { detail: "La contraseña actual es incorrecta" },
      },
    });

    renderDialog();
    await fillAndSubmit();

    await waitFor(() =>
      expect(toastError).toHaveBeenCalledWith(
        "La contraseña actual es incorrecta",
      ),
    );
    expect(toastError).not.toHaveBeenCalledWith(
      "Request failed with status code 400",
    );
  });

  it("falls back to a generic Spanish message when no detail is present", async () => {
    vi.mocked(apiClient.post).mockRejectedValue({
      message: "Network Error",
      response: { status: 500, data: {} },
    });

    renderDialog();
    await fillAndSubmit();

    await waitFor(() =>
      expect(toastError).toHaveBeenCalledWith("Error al cambiar la contraseña"),
    );
  });
});
