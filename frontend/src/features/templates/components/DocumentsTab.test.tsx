import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { DocumentsTab } from "./DocumentsTab";
import { apiClient } from "@/shared/lib/api-client";

vi.mock("@/shared/lib/api-client", () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}));

// DownloadButton / GroupZipDownload read the current role via useAuth. Keep it
// mutable so a single test can exercise the admin (Word ZIP) branch.
const authState = vi.hoisted(() => ({ role: "user" }));
vi.mock("@/shared/lib/auth", () => ({
  useAuth: () => ({ user: { role: authState.role } }),
}));

const primaryDoc = {
  id: "doc-1",
  template_version_id: "version-1",
  template_id: "template-1",
  template_name: "Contrato de Servicios",
  template_version: 2,
  docx_file_name: "alice.docx",
  pdf_file_name: "alice.pdf",
  generation_type: "single",
  status: "completed",
  download_url: null,
  variables_snapshot: { name: "Alice" },
  created_at: "2026-01-01T00:00:00Z",
  group_id: "grp-1",
  related_label: null,
};

const relatedDocA = {
  ...primaryDoc,
  id: "doc-2",
  docx_file_name: "recibo.docx",
  pdf_file_name: "recibo.pdf",
  related_label: "Recibo de pago",
};

const relatedDocB = {
  ...primaryDoc,
  id: "doc-3",
  docx_file_name: "anexo.docx",
  pdf_file_name: "anexo.pdf",
  related_label: "Anexo A",
};

const groupWithRelated = {
  group_id: "grp-1",
  primary: primaryDoc,
  related: [relatedDocA, relatedDocB],
};

const standaloneGroup = {
  group_id: null,
  primary: { ...primaryDoc, id: "doc-9", docx_file_name: "solo.docx", group_id: null },
  related: [],
};

function mockGroupsResponse(items: unknown[] = [groupWithRelated]) {
  vi.mocked(apiClient.get).mockResolvedValue({
    data: { items, total: items.length, page: 1, size: 20 },
  });
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
      <DocumentsTab templateId="template-1" />
    </QueryClientProvider>,
  );
}

describe("DocumentsTab — grouped documents", () => {
  beforeEach(() => {
    authState.role = "user";
    vi.mocked(apiClient.get).mockReset();
    mockGroupsResponse();
    // triggerBlobDownload uses object URLs — jsdom has no layout engine, so
    // stub them the same way TemplateDetail/FullDocumentEditor tests do.
    URL.createObjectURL = vi.fn(
      () => "blob:mock-url",
    ) as unknown as typeof URL.createObjectURL;
    URL.revokeObjectURL = vi.fn();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("queries the grouped endpoint and renders the primary document row", async () => {
    renderTab();

    await waitFor(() =>
      expect(screen.getByText("alice.docx")).toBeInTheDocument(),
    );

    expect(apiClient.get).toHaveBeenCalledWith(
      "/documents/groups?page=1&size=20&template_id=template-1",
    );
    expect(
      screen.getByRole("columnheader", { name: /versión/i }),
    ).toBeInTheDocument();
    expect(screen.getByText("v2")).toBeInTheDocument();
  });

  it("collapses related documents behind an expander, revealed on click", async () => {
    const user = userEvent.setup();
    renderTab();

    await waitFor(() =>
      expect(screen.getByText("alice.docx")).toBeInTheDocument(),
    );

    // Related labels are hidden until the group is expanded.
    expect(screen.queryByText("Recibo de pago")).not.toBeInTheDocument();
    expect(screen.queryByText("Anexo A")).not.toBeInTheDocument();

    const expander = screen.getByRole("button", {
      name: /2 documentos relacionados/i,
    });
    await user.click(expander);

    expect(screen.getByText("Recibo de pago")).toBeInTheDocument();
    expect(screen.getByText("Anexo A")).toBeInTheDocument();
  });

  it("shows no expander or ZIP action for a standalone document", async () => {
    mockGroupsResponse([standaloneGroup]);
    renderTab();

    await waitFor(() =>
      expect(screen.getByText("solo.docx")).toBeInTheDocument(),
    );

    expect(
      screen.queryByRole("button", { name: /documentos relacionados/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /descargar todo \(zip\)/i }),
    ).not.toBeInTheDocument();
  });

  it("downloads the group PDF ZIP for a non-admin", async () => {
    const user = userEvent.setup();
    renderTab();

    await waitFor(() =>
      expect(screen.getByText("alice.docx")).toBeInTheDocument(),
    );

    await user.click(
      screen.getByRole("button", { name: /descargar todo \(zip\)/i }),
    );

    await waitFor(() =>
      expect(apiClient.get).toHaveBeenCalledWith(
        "/documents/groups/grp-1/download?format=pdf",
        { responseType: "blob" },
      ),
    );
  });

  it("lets an admin download the group Word ZIP", async () => {
    authState.role = "admin";
    const user = userEvent.setup();
    renderTab();

    await waitFor(() =>
      expect(screen.getByText("alice.docx")).toBeInTheDocument(),
    );

    await user.click(
      screen.getByRole("button", { name: /descargar todo \(zip\)/i }),
    );
    await user.click(
      await screen.findByRole("menuitem", { name: /paquete word/i }),
    );

    await waitFor(() =>
      expect(apiClient.get).toHaveBeenCalledWith(
        "/documents/groups/grp-1/download?format=docx",
        { responseType: "blob" },
      ),
    );
  });
});
