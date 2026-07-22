import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { DynamicForm } from "./DynamicForm";
import { apiClient } from "@/shared/lib/api-client";

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

function renderForm() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  // Three variables (< 4) route to the flat fallback form. One is computed.
  return render(
    <QueryClientProvider client={queryClient}>
      <DynamicForm
        templateVersionId="version-1"
        variables={["cliente", "monto", "total_letras"]}
        variablesMeta={[
          { name: "cliente", contexts: [] },
          { name: "monto", contexts: [] },
          {
            name: "total_letras",
            contexts: [],
            computed: { kind: "function" },
          },
        ]}
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

describe("DynamicForm (flat fallback) — computed variables", () => {
  it("does not render an input for the computed variable", () => {
    renderForm();

    expect(screen.getByPlaceholderText("Ingrese cliente")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Ingrese monto")).toBeInTheDocument();
    // The computed variable must not appear as a required field.
    expect(
      screen.queryByPlaceholderText("Ingrese total_letras"),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("total_letras")).not.toBeInTheDocument();
  });

  it("submits only the editable variables (computed excluded) without forcing a value for it", async () => {
    const user = userEvent.setup();
    renderForm();

    // Filling ONLY the two editable fields must satisfy the schema — the
    // computed variable is never required.
    await user.type(screen.getByPlaceholderText("Ingrese cliente"), "Acme");
    await user.type(screen.getByPlaceholderText("Ingrese monto"), "1000");
    await user.click(
      screen.getByRole("button", { name: /generar documento/i }),
    );

    await waitFor(() => expect(apiClient.post).toHaveBeenCalled());
    expect(apiClient.post).toHaveBeenCalledWith("/documents/generate", {
      template_version_id: "version-1",
      variables: { cliente: "Acme", monto: "1000" },
    });
  });
});
