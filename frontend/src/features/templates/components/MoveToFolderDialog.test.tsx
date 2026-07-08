import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { MoveToFolderDialog } from "./MoveToFolderDialog";
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

function mockFoldersResponse() {
  vi.mocked(apiClient.get).mockResolvedValue({
    data: {
      folders: [
        { id: "folder-1", name: "Contratos", template_count: 3 },
        { id: "folder-2", name: "Informes", template_count: 5 },
      ],
    },
  });
}

function renderDialog(
  props: Partial<React.ComponentProps<typeof MoveToFolderDialog>> = {},
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
      <MoveToFolderDialog
        templateId="template-1"
        templateName="Contrato de Servicios"
        currentFolderId="folder-1"
        open
        onOpenChange={onOpenChange}
        {...props}
      />
    </QueryClientProvider>,
  );
  return { onOpenChange };
}

describe("MoveToFolderDialog", () => {
  beforeEach(() => {
    vi.mocked(apiClient.get).mockReset();
    vi.mocked(apiClient.patch).mockReset();
    toastSuccess.mockReset();
    toastError.mockReset();
    mockFoldersResponse();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("preselects the template's current folder", async () => {
    renderDialog({ currentFolderId: "folder-1" });

    await waitFor(() =>
      expect(screen.getByRole("combobox")).toBeInTheDocument(),
    );
    await waitFor(() =>
      expect(screen.getByRole("combobox")).toHaveTextContent("Contratos"),
    );
  });

  it("submits a PATCH with the chosen folder's id when a different folder is picked", async () => {
    vi.mocked(apiClient.patch).mockResolvedValue({ data: {} });
    const user = userEvent.setup();
    renderDialog({ currentFolderId: "folder-1" });

    const combobox = await screen.findByRole("combobox");
    await user.click(combobox);
    const option = await screen.findByRole("option", { name: "Informes" });
    await user.click(option);

    await user.click(screen.getByRole("button", { name: /^mover$/i }));

    await waitFor(() =>
      expect(apiClient.patch).toHaveBeenCalledWith("/templates/template-1", {
        folder_id: "folder-2",
      }),
    );
    await waitFor(() =>
      expect(toastSuccess).toHaveBeenCalledWith("Plantilla movida con éxito"),
    );
  });

  it('submits folder_id: null when "Sin carpeta" is chosen', async () => {
    vi.mocked(apiClient.patch).mockResolvedValue({ data: {} });
    const user = userEvent.setup();
    renderDialog({ currentFolderId: "folder-1" });

    const combobox = await screen.findByRole("combobox");
    await user.click(combobox);
    const option = await screen.findByRole("option", { name: "Sin carpeta" });
    await user.click(option);

    await user.click(screen.getByRole("button", { name: /^mover$/i }));

    await waitFor(() =>
      expect(apiClient.patch).toHaveBeenCalledWith("/templates/template-1", {
        folder_id: null,
      }),
    );
  });

  it('seeds "Sin carpeta" and submits folder_id: null when currentFolderId is not among the loaded folders (orphaned reference)', async () => {
    vi.mocked(apiClient.patch).mockResolvedValue({ data: {} });
    const user = userEvent.setup();
    renderDialog({ currentFolderId: "folder-orphaned-not-in-list" });

    await waitFor(() =>
      expect(screen.getByRole("combobox")).toHaveTextContent("Sin carpeta"),
    );

    await user.click(screen.getByRole("button", { name: /^mover$/i }));

    await waitFor(() =>
      expect(apiClient.patch).toHaveBeenCalledWith("/templates/template-1", {
        folder_id: null,
      }),
    );
  });
});
