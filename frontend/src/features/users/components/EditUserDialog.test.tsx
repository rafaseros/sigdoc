import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { EditUserDialog } from "./EditUserDialog";
import { apiClient } from "@/shared/lib/api-client";

vi.mock("@/shared/lib/api-client", () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}));

const toastSuccess = vi.fn();
const toastError = vi.fn();
const toastInfo = vi.fn();

vi.mock("sonner", () => ({
  toast: {
    success: (...args: unknown[]) => toastSuccess(...args),
    error: (...args: unknown[]) => toastError(...args),
    info: (...args: unknown[]) => toastInfo(...args),
  },
}));

// Editing self as admin keeps the role picker hidden, so the test only
// exercises the name update + error path.
vi.mock("@/shared/lib/auth", () => ({
  useAuth: () => ({ user: { id: "user-1", role: "admin" } }),
}));

const editedUser = {
  id: "user-1",
  email: "ana@empresa.com",
  full_name: "Ana Pérez",
  role: "admin",
  is_active: true,
  created_at: "2026-01-01T00:00:00Z",
};

function renderDialog() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  render(
    <QueryClientProvider client={queryClient}>
      <EditUserDialog user={editedUser} open onOpenChange={vi.fn()} />
    </QueryClientProvider>,
  );
}

describe("EditUserDialog — error handling", () => {
  beforeEach(() => {
    vi.mocked(apiClient.put).mockReset();
    toastSuccess.mockReset();
    toastError.mockReset();
    toastInfo.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("surfaces the backend Spanish detail instead of the raw axios message", async () => {
    vi.mocked(apiClient.put).mockRejectedValue({
      message: "Request failed with status code 400",
      response: {
        status: 400,
        data: { detail: "El nombre completo no es válido" },
      },
    });

    const user = userEvent.setup();
    renderDialog();

    const nameInput = screen.getByLabelText(/nombre completo/i);
    await user.clear(nameInput);
    await user.type(nameInput, "Ana María Pérez");
    await user.click(screen.getByRole("button", { name: /guardar cambios/i }));

    await waitFor(() =>
      expect(toastError).toHaveBeenCalledWith("El nombre completo no es válido"),
    );
    expect(toastError).not.toHaveBeenCalledWith(
      "Request failed with status code 400",
    );
  });
});
