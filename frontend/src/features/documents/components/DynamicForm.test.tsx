import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { DynamicForm } from "./DynamicForm";
import { apiClient } from "@/shared/lib/api-client";
import type { TemplateVersionFile } from "@/features/templates/api/queries";

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

function renderFlatVariant() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  // Five variables (>= 4) would normally route to the InlineDocumentEditor,
  // but variant="flat" must force the plain flat form regardless of count.
  return render(
    <QueryClientProvider client={queryClient}>
      <DynamicForm
        variant="flat"
        templateVersionId="version-1"
        variables={["alpha", "beta", "gamma", "delta", "epsilon"]}
        variablesMeta={[
          { name: "alpha", contexts: [] },
          { name: "beta", contexts: [] },
          { name: "gamma", contexts: [] },
          { name: "delta", contexts: [] },
          { name: "epsilon", contexts: [] },
        ]}
        templateName="Big Template"
      />
    </QueryClientProvider>,
  );
}

describe("DynamicForm — variant='flat'", () => {
  it("renders the plain flat form (not the inline editor) even with >= 4 variables", () => {
    renderFlatVariant();

    // Flat-form marker heading.
    expect(screen.getByText("Complete las variables")).toBeInTheDocument();
    // InlineDocumentEditor marker header must never appear.
    expect(screen.queryByText("Completar variables")).not.toBeInTheDocument();

    // Every variable is a plain input in the flat form.
    for (const name of ["alpha", "beta", "gamma", "delta", "epsilon"]) {
      expect(
        screen.getByPlaceholderText(`Ingrese ${name}`),
      ).toBeInTheDocument();
    }
  });
});

function renderVariant(variant: "flat" | "fields") {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  // One field carries both a document context and help text so the two display
  // modes can be told apart; one field is computed (must never render an input).
  return render(
    <QueryClientProvider client={queryClient}>
      <DynamicForm
        variant={variant}
        templateVersionId="version-1"
        variables={["cliente", "monto", "total_letras"]}
        variablesMeta={[
          {
            name: "cliente",
            contexts: ["Contexto documental: {{cliente}}"],
            help_text: "Nombre legal completo del cliente",
          },
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

describe("DynamicForm — variant='flat' shows document context", () => {
  it("renders the ContextPreview and not the help text", () => {
    renderVariant("flat");

    // The document context (where the value lands) is shown...
    expect(screen.getByText(/Contexto documental/)).toBeInTheDocument();
    // ...and the help text is NOT shown in the guided/context display.
    expect(
      screen.queryByText("Nombre legal completo del cliente"),
    ).not.toBeInTheDocument();

    // Computed variable is still excluded.
    expect(
      screen.queryByPlaceholderText("Ingrese total_letras"),
    ).not.toBeInTheDocument();
  });
});

describe("DynamicForm — variant='fields' shows help text only", () => {
  it("renders the help text and hides the ContextPreview", () => {
    renderVariant("fields");

    // Help text is shown as the field description...
    expect(
      screen.getByText("Nombre legal completo del cliente"),
    ).toBeInTheDocument();
    // ...and no document context appears at all.
    expect(screen.queryByText(/Contexto documental/)).not.toBeInTheDocument();

    // Editable fields are still plain inputs.
    expect(screen.getByPlaceholderText("Ingrese cliente")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Ingrese monto")).toBeInTheDocument();

    // Computed variable is still excluded.
    expect(
      screen.queryByPlaceholderText("Ingrese total_letras"),
    ).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Related-file provenance — each rendered field surfaces which RELATED files
// also use its variable (derived from `files[].variables`), in BOTH the guided
// (variant="flat") and quick (variant="fields") display modes.
// ---------------------------------------------------------------------------

function renderProvenance(variant: "flat" | "fields") {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  // 'Anexo A' uses `cliente` (editable) and `total_letras` (computed). `monto`
  // is used by no related file. The computed variable is never rendered as a
  // field, so it must never surface a provenance chip either.
  const files: TemplateVersionFile[] = [
    {
      id: "file-1",
      label: "Anexo A",
      variables: ["cliente", "total_letras"],
      file_size: 2048,
      position: 0,
      created_at: "2026-01-01T00:00:00Z",
    },
  ];
  return render(
    <QueryClientProvider client={queryClient}>
      <DynamicForm
        variant={variant}
        templateVersionId="version-1"
        variables={["cliente", "monto", "total_letras"]}
        variablesMeta={[
          {
            name: "cliente",
            contexts: ["Contexto documental: {{cliente}}"],
            help_text: "Nombre legal completo del cliente",
          },
          { name: "monto", contexts: [] },
          {
            name: "total_letras",
            contexts: [],
            computed: { kind: "function" },
          },
        ]}
        templateName="Test Template"
        files={files}
      />
    </QueryClientProvider>,
  );
}

describe("DynamicForm — related-file provenance", () => {
  it("shows the 'También en:' provenance under a field a related file uses (variant='flat'/Guiado)", () => {
    renderProvenance("flat");

    // 'cliente' is used by 'Anexo A' → its field carries the provenance line.
    expect(screen.getByText("También en:")).toBeInTheDocument();
    // Rendered exactly once: 'monto' is in no file and the computed
    // 'total_letras' field is never rendered, so neither adds a chip.
    expect(screen.getAllByText("Anexo A")).toHaveLength(1);
    expect(screen.getAllByText("También en:")).toHaveLength(1);
  });

  it("shows the 'También en:' provenance under a field a related file uses (variant='fields'/Rápido)", () => {
    renderProvenance("fields");

    expect(screen.getByText("También en:")).toBeInTheDocument();
    expect(screen.getAllByText("Anexo A")).toHaveLength(1);
    expect(screen.getAllByText("También en:")).toHaveLength(1);
  });

  it("keeps the computed variable excluded even when a related file uses it", () => {
    renderProvenance("flat");

    // The computed variable is still never rendered as an input, so its
    // provenance chip is never shown either — only 'cliente' carries one.
    expect(
      screen.queryByPlaceholderText("Ingrese total_letras"),
    ).not.toBeInTheDocument();
    expect(screen.getAllByText("También en:")).toHaveLength(1);
  });
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
