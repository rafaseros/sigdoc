import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { RenameTemplateDialog } from "./RenameTemplateDialog";
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

function renderDialog(
  props: Partial<React.ComponentProps<typeof RenameTemplateDialog>> = {},
) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  const onOpenChange = vi.fn();
  render(
    <QueryClientProvider client={queryClient}>
      <RenameTemplateDialog
        templateId="template-1"
        currentName="Contrato de servicios"
        currentDescription="Descripción original"
        open
        onOpenChange={onOpenChange}
        {...props}
      />
    </QueryClientProvider>,
  );
  return { onOpenChange };
}

describe("RenameTemplateDialog", () => {
  beforeEach(() => {
    vi.mocked(apiClient.patch).mockReset();
    toastSuccess.mockReset();
    toastError.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("submits a PATCH with the new name and shows a success toast", async () => {
    vi.mocked(apiClient.patch).mockResolvedValue({
      data: {
        id: "template-1",
        name: "Contrato revisado",
        description: "Descripción original",
      },
    });
    const user = userEvent.setup();
    renderDialog();

    const nameInput = screen.getByLabelText(/nombre/i);
    await user.clear(nameInput);
    await user.type(nameInput, "Contrato revisado");

    await user.click(screen.getByRole("button", { name: /guardar cambios/i }));

    await waitFor(() =>
      expect(apiClient.patch).toHaveBeenCalledWith("/templates/template-1", {
        name: "Contrato revisado",
      }),
    );
    await waitFor(() =>
      expect(toastSuccess).toHaveBeenCalledWith(
        "Plantilla renombrada con éxito",
      ),
    );
  });

  it("disables the submit button when the name is unchanged", () => {
    renderDialog();

    expect(
      screen.getByRole("button", { name: /guardar cambios/i }),
    ).toBeDisabled();
  });

  it("disables the submit button when the name is cleared to empty", async () => {
    const user = userEvent.setup();
    renderDialog();

    const nameInput = screen.getByLabelText(/nombre/i);
    await user.clear(nameInput);

    expect(
      screen.getByRole("button", { name: /guardar cambios/i }),
    ).toBeDisabled();
  });

  it("surfaces a 409 backend collision detail as an error toast", async () => {
    vi.mocked(apiClient.patch).mockRejectedValue({
      response: {
        status: 409,
        data: { detail: "Ya existe una plantilla con ese nombre" },
      },
    });
    const user = userEvent.setup();
    renderDialog();

    const nameInput = screen.getByLabelText(/nombre/i);
    await user.clear(nameInput);
    await user.type(nameInput, "Nombre duplicado");
    await user.click(screen.getByRole("button", { name: /guardar cambios/i }));

    await waitFor(() =>
      expect(toastError).toHaveBeenCalledWith(
        "Ya existe una plantilla con ese nombre",
      ),
    );
  });
});
