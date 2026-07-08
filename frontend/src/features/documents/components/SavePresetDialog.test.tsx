import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { SavePresetDialog } from "./SavePresetDialog";
import { apiClient } from "@/shared/lib/api-client";

vi.mock("@/shared/lib/api-client", () => ({
  apiClient: {
    post: vi.fn(),
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
  props: Partial<React.ComponentProps<typeof SavePresetDialog>> = {},
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
      <SavePresetDialog
        templateId="template-1"
        values={{ company_name: "Acme Corp", item_count: "42" }}
        open
        onOpenChange={onOpenChange}
        {...props}
      />
    </QueryClientProvider>,
  );
  return { onOpenChange };
}

describe("SavePresetDialog", () => {
  beforeEach(() => {
    vi.mocked(apiClient.post).mockReset();
    toastSuccess.mockReset();
    toastError.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("posts the entered name plus the current non-empty values passed in via props", async () => {
    vi.mocked(apiClient.post).mockResolvedValue({ data: { id: "preset-1" } });
    const user = userEvent.setup();
    const { onOpenChange } = renderDialog();

    await user.type(screen.getByLabelText("Nombre"), "Cliente Acme");
    await user.click(screen.getByRole("button", { name: /^guardar$/i }));

    expect(apiClient.post).toHaveBeenCalledWith(
      "/templates/template-1/presets",
      {
        name: "Cliente Acme",
        values: { company_name: "Acme Corp", item_count: "42" },
      },
    );
    expect(toastSuccess).toHaveBeenCalledWith("Datos «Cliente Acme» guardados");
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("drops empty values before posting", async () => {
    vi.mocked(apiClient.post).mockResolvedValue({ data: { id: "preset-1" } });
    const user = userEvent.setup();
    renderDialog({ values: { company_name: "Acme Corp", item_count: "" } });

    await user.type(screen.getByLabelText("Nombre"), "Cliente Acme");
    await user.click(screen.getByRole("button", { name: /^guardar$/i }));

    expect(apiClient.post).toHaveBeenCalledWith(
      "/templates/template-1/presets",
      {
        name: "Cliente Acme",
        values: { company_name: "Acme Corp" },
      },
    );
  });

  it("shows the backend's Spanish duplicate-name detail on a 409 response", async () => {
    vi.mocked(apiClient.post).mockRejectedValue({
      response: { data: { detail: "Ya existe un dato guardado con ese nombre" } },
    });
    const user = userEvent.setup();
    const { onOpenChange } = renderDialog();

    await user.type(screen.getByLabelText("Nombre"), "Cliente Acme");
    await user.click(screen.getByRole("button", { name: /^guardar$/i }));

    expect(toastError).toHaveBeenCalledWith(
      "Ya existe un dato guardado con ese nombre",
    );
    expect(onOpenChange).not.toHaveBeenCalledWith(false);
  });
});
