import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { InlineDocumentEditor } from "./InlineDocumentEditor";
import { apiClient } from "@/shared/lib/api-client";
import type { VariableMeta } from "@/lib/assemble-document";

// DownloadButton (rendered after a successful generate) reads the current
// role via useAuth — provide a stub non-admin user.
vi.mock("@/shared/lib/auth", () => ({
  useAuth: () => ({ user: { role: "user" } }),
}));

vi.mock("@/shared/lib/api-client", () => ({
  apiClient: {
    post: vi.fn(),
    get: vi.fn(),
  },
}));

const toastSuccessMock = vi.fn();
const toastErrorMock = vi.fn();
vi.mock("sonner", () => ({
  toast: {
    success: (...args: unknown[]) => toastSuccessMock(...args),
    error: (...args: unknown[]) => toastErrorMock(...args),
  },
}));

// Four variables — three editable, one server-computed (function-kind). The
// computed one must never count toward progress nor reach the payload.
const variablesMeta: VariableMeta[] = [
  {
    name: "cliente",
    contexts: ["Contrato con {{ cliente }} por {{ monto }}."],
  },
  {
    name: "monto",
    contexts: ["Contrato con {{ cliente }} por {{ monto }}."],
  },
  { name: "fecha", contexts: ["Firmado el {{ fecha }}."] },
  {
    name: "monto_en_letras",
    contexts: ["Total: {{ monto_en_letras }}."],
    computed: { kind: "function" },
  },
];

function renderInline(meta: VariableMeta[] = variablesMeta) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <InlineDocumentEditor
        templateVersionId="version-1"
        variablesMeta={meta}
        templateName="Test Template"
      />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.mocked(apiClient.post).mockReset();
  vi.mocked(apiClient.post).mockResolvedValue({
    data: {
      documents: [
        {
          id: "doc-1",
          template_version_id: "version-1",
          docx_file_name: "contrato.docx",
          pdf_file_name: null,
          generation_type: "single",
          status: "completed",
          download_url: null,
          variables_snapshot: {},
          created_at: "2026-01-01T00:00:00Z",
          group_id: null,
        },
      ],
      group_id: null,
    },
  });
  toastSuccessMock.mockReset();
  toastErrorMock.mockReset();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("InlineDocumentEditor — computed variables", () => {
  it("does not require the computed variable: filling only the editable ones enables generation", async () => {
    const user = userEvent.setup();
    renderInline();

    const generateButton = screen.getByRole("button", {
      name: /generar documento/i,
    });
    expect(generateButton).toBeDisabled();

    // The computed placeholder still renders (fallback keeps it visible) but
    // is never demanded.
    expect(screen.getByText("monto en letras")).toBeInTheDocument();

    // Fill only the three editable variables. Auto-advance walks between them
    // and must skip the computed placeholder entirely.
    await user.click(screen.getByText("cliente"));
    await user.type(screen.getByRole("textbox"), "Acme");
    await user.keyboard("{Enter}");
    await user.type(screen.getByRole("textbox"), "1000");
    await user.keyboard("{Enter}");
    await user.type(screen.getByRole("textbox"), "2026-01-01");
    await user.keyboard("{Enter}");

    // All editable variables filled → ready, even though the computed one is
    // still empty. Proves computed never counted toward totalCount/allFilled.
    expect(screen.getByText(/listo para generar/i)).toBeInTheDocument();
    expect(generateButton).toBeEnabled();
  });

  it("excludes the computed variable from the generate payload", async () => {
    const user = userEvent.setup();
    renderInline();

    await user.click(screen.getByText("cliente"));
    await user.type(screen.getByRole("textbox"), "Acme");
    await user.keyboard("{Enter}");
    await user.type(screen.getByRole("textbox"), "1000");
    await user.keyboard("{Enter}");
    await user.type(screen.getByRole("textbox"), "2026-01-01");
    await user.keyboard("{Enter}");

    await user.click(
      screen.getByRole("button", { name: /generar documento/i }),
    );

    await waitFor(() => expect(apiClient.post).toHaveBeenCalled());
    expect(apiClient.post).toHaveBeenCalledWith("/documents/generate", {
      template_version_id: "version-1",
      variables: { cliente: "Acme", monto: "1000", fecha: "2026-01-01" },
    });
  });
});
