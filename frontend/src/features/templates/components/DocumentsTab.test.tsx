import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
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

// DownloadButton reads the current role via useAuth — provide a stub user.
vi.mock("@/shared/lib/auth", () => ({
  useAuth: () => ({ user: { role: "user" } }),
}));

const documentItem = {
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
};

function mockDocumentsResponse() {
  vi.mocked(apiClient.get).mockResolvedValue({
    data: { items: [documentItem], total: 1, page: 1, size: 20 },
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

describe("DocumentsTab — version column", () => {
  beforeEach(() => {
    vi.mocked(apiClient.get).mockReset();
    mockDocumentsResponse();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders a 'Versión' column with a v{n} badge per document row", async () => {
    renderTab();

    await waitFor(() =>
      expect(screen.getByText("alice.docx")).toBeInTheDocument(),
    );

    expect(
      screen.getByRole("columnheader", { name: /versión/i }),
    ).toBeInTheDocument();
    expect(screen.getByText("v2")).toBeInTheDocument();
  });
});
