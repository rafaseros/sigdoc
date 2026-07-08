import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { PresetsTab } from "./PresetsTab";
import { apiClient } from "@/shared/lib/api-client";
import type { VariableMeta } from "@/features/templates/api/queries";

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

const variablesMeta: VariableMeta[] = [
  { name: "company_name", contexts: [], type: "text" },
  { name: "amount", contexts: [], type: "decimal" },
  // Computed — must never appear as a field in the create/edit form.
  {
    name: "amount_with_surcharge",
    contexts: [],
    type: "decimal",
    computed: { kind: "formula", source: "amount", operator: "+", operand: 50 },
  },
];

function mockPresetsResponse(presets: unknown[] = []) {
  vi.mocked(apiClient.get).mockResolvedValue({ data: { presets } });
}

function renderTab() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <PresetsTab templateId="template-1" variablesMeta={variablesMeta} />
    </QueryClientProvider>,
  );
}

describe("PresetsTab", () => {
  beforeEach(() => {
    vi.mocked(apiClient.get).mockReset();
    vi.mocked(apiClient.post).mockReset();
    vi.mocked(apiClient.delete).mockReset();
    toastSuccess.mockReset();
    toastError.mockReset();
    mockPresetsResponse();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows an empty state when the template has no saved presets", async () => {
    renderTab();
    expect(
      await screen.findByText("Todavía no hay datos guardados para esta plantilla."),
    ).toBeInTheDocument();
  });

  it("lists existing presets with their value count and creation date", async () => {
    mockPresetsResponse([
      {
        id: "preset-1",
        name: "Cliente Acme",
        values: { company_name: "Acme Corp", amount: "100" },
        created_by: "user-1",
        created_at: "2026-01-15T00:00:00Z",
      },
    ]);
    renderTab();

    expect(await screen.findByText("Cliente Acme")).toBeInTheDocument();
    expect(screen.getByText(/2 valores/)).toBeInTheDocument();
  });

  it("'Nuevo' opens a create dialog with one input per non-computed variable and posts the right shape", async () => {
    vi.mocked(apiClient.post).mockResolvedValue({ data: { id: "preset-1" } });
    const user = userEvent.setup();
    renderTab();

    await user.click(screen.getByRole("button", { name: /^nuevo$/i }));

    expect(screen.getByLabelText("company_name")).toBeInTheDocument();
    expect(screen.getByLabelText("amount")).toBeInTheDocument();
    // Computed variable must never get a field in the form.
    expect(
      screen.queryByLabelText("amount_with_surcharge"),
    ).not.toBeInTheDocument();

    await user.type(screen.getByLabelText("Nombre"), "Cliente Beta");
    await user.type(screen.getByLabelText("company_name"), "Beta LLC");
    await user.type(screen.getByLabelText("amount"), "250");

    await user.click(screen.getByRole("button", { name: /^crear$/i }));

    await waitFor(() =>
      expect(apiClient.post).toHaveBeenCalledWith(
        "/templates/template-1/presets",
        {
          name: "Cliente Beta",
          values: { company_name: "Beta LLC", amount: "250" },
        },
      ),
    );
  });

  it("deletes a preset after inline confirmation", async () => {
    mockPresetsResponse([
      {
        id: "preset-1",
        name: "Cliente Acme",
        values: { company_name: "Acme Corp" },
        created_by: "user-1",
        created_at: "2026-01-15T00:00:00Z",
      },
    ]);
    vi.mocked(apiClient.delete).mockResolvedValue({ data: undefined });
    const user = userEvent.setup();
    renderTab();

    await screen.findByText("Cliente Acme");
    await user.click(screen.getByRole("button", { name: /^eliminar$/i }));

    // Inline confirm — clicking "Eliminar" once only reveals a confirm step.
    expect(apiClient.delete).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: /^confirmar$/i }));

    await waitFor(() =>
      expect(apiClient.delete).toHaveBeenCalledWith(
        "/templates/template-1/presets/preset-1",
      ),
    );
    expect(toastSuccess).toHaveBeenCalledWith(
      "Datos «Cliente Acme» eliminados",
    );
  });
});
