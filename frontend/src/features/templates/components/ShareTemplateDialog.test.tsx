import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { ShareTemplateDialog } from "./ShareTemplateDialog";
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
const toastInfo = vi.fn();

vi.mock("sonner", () => ({
  toast: {
    success: (...args: unknown[]) => toastSuccess(...args),
    error: (...args: unknown[]) => toastError(...args),
    info: (...args: unknown[]) => toastInfo(...args),
  },
}));

function share(userId: string, email: string) {
  return {
    id: `share-${userId}`,
    template_id: "template-1",
    user_id: userId,
    user_email: email,
    tenant_id: "tenant-1",
    shared_by: "owner-1",
    shared_at: "2026-01-01T00:00:00Z",
  };
}

function renderDialog() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  render(
    <QueryClientProvider client={queryClient}>
      <ShareTemplateDialog
        templateId="template-1"
        templateName="Contrato de Servicios"
        open
        onOpenChange={vi.fn()}
      />
    </QueryClientProvider>,
  );
}

async function submitEmail(email: string) {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText(/agregar usuario por correo/i), email);
  await user.click(screen.getByRole("button", { name: /compartir/i }));
}

describe("ShareTemplateDialog — share status mapping", () => {
  beforeEach(() => {
    vi.mocked(apiClient.get).mockReset();
    vi.mocked(apiClient.post).mockReset();
    toastSuccess.mockReset();
    toastError.mockReset();
    toastInfo.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows a success toast when a new user is shared", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: [] });
    vi.mocked(apiClient.post).mockResolvedValue({
      data: share("user-2", "nuevo@empresa.com"),
    });

    renderDialog();
    await waitFor(() => expect(apiClient.get).toHaveBeenCalled());
    await submitEmail("nuevo@empresa.com");

    await waitFor(() =>
      expect(toastSuccess).toHaveBeenCalledWith(
        "Plantilla compartida con éxito",
      ),
    );
    expect(toastInfo).not.toHaveBeenCalled();
  });

  it("shows an idempotent 'already shared' info toast when the user was already in the list", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({
      data: [share("user-1", "existente@empresa.com")],
    });
    // Idempotent backend returns the pre-existing share (same user_id).
    vi.mocked(apiClient.post).mockResolvedValue({
      data: share("user-1", "existente@empresa.com"),
    });

    renderDialog();
    // Ensure the existing share is loaded before we submit.
    await waitFor(() =>
      expect(screen.getByText("existente@empresa.com")).toBeInTheDocument(),
    );
    await submitEmail("existente@empresa.com");

    await waitFor(() =>
      expect(toastInfo).toHaveBeenCalledWith(
        "Esta plantilla ya estaba compartida con ese usuario",
      ),
    );
    expect(toastSuccess).not.toHaveBeenCalled();
  });

  it("surfaces the backend detail on a real 422 sharing error", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: [] });
    vi.mocked(apiClient.post).mockRejectedValue({
      response: {
        status: 422,
        data: {
          detail:
            "No se puede compartir una plantilla con un usuario de otro tenant",
        },
      },
    });

    renderDialog();
    await waitFor(() => expect(apiClient.get).toHaveBeenCalled());
    await submitEmail("otro@tenant.com");

    await waitFor(() =>
      expect(toastError).toHaveBeenCalledWith(
        "No se puede compartir una plantilla con un usuario de otro tenant",
      ),
    );
  });

  it("shows the fixed not-found message on a 404", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: [] });
    vi.mocked(apiClient.post).mockRejectedValue({
      response: {
        status: 404,
        data: { detail: "No se encontró un usuario con ese correo" },
      },
    });

    renderDialog();
    await waitFor(() => expect(apiClient.get).toHaveBeenCalled());
    await submitEmail("desconocido@empresa.com");

    await waitFor(() =>
      expect(toastError).toHaveBeenCalledWith(
        "No se encontró un usuario con ese correo",
      ),
    );
  });
});
