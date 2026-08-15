import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// TanStack Router: expose Route.useParams/useSearch and stub navigation/Link
// so the page component renders standalone.
vi.mock("@tanstack/react-router", () => ({
  createFileRoute: () => (options: Record<string, unknown>) => ({
    ...options,
    useParams: () => ({ versionId: "version-1" }),
    useSearch: () => ({ templateId: "template-1" }),
  }),
  useNavigate: () => vi.fn(),
  Link: ({ children }: { children: React.ReactNode }) => <a>{children}</a>,
}));

// Query hooks — swapped per test via the mocks below.
const useTemplateMock = vi.fn();
const useTemplateStructureMock = vi.fn();
vi.mock("@/features/templates/api/queries", () => ({
  useTemplate: () => useTemplateMock(),
  useTemplateStructure: () => useTemplateStructureMock(),
}));

// Editors are stubbed to lightweight markers so this test stays focused on the
// mode-selection logic, not the editors' internals.
vi.mock("@/features/documents/components/FullDocumentEditor", () => ({
  FullDocumentEditor: () => <div data-testid="full-editor" />,
}));
vi.mock("@/features/documents/components/DynamicForm", () => ({
  DynamicForm: (props: { variant?: string; files?: unknown[] }) => (
    <div
      data-testid="dynamic-form"
      data-variant={props.variant}
      data-file-count={props.files?.length ?? 0}
    />
  ),
}));

import { GeneratePage } from "./$versionId";
import { GENERATE_MODE_STORAGE_KEY } from "@/features/documents/lib/useGenerateMode";

const template = {
  id: "template-1",
  name: "Contrato",
  current_version: 1,
  variables: ["nombre", "monto"],
  versions: [
    {
      id: "version-1",
      version: 1,
      variables: ["nombre", "monto"],
      variables_meta: [
        { name: "nombre", contexts: [] },
        { name: "monto", contexts: [] },
      ],
      files: [],
    },
  ],
};

beforeEach(() => {
  window.localStorage.clear();
  useTemplateMock.mockReturnValue({ data: template, isLoading: false });
  useTemplateStructureMock.mockReturnValue({
    data: { paragraphs: [] },
    isLoading: false,
    isError: false,
  });
});

afterEach(() => {
  vi.clearAllMocks();
  window.localStorage.clear();
});

describe("GeneratePage — generation mode toggle", () => {
  it("offers three modes and defaults to the full document editor", () => {
    render(<GeneratePage />);

    // All three levels are present, in order.
    expect(screen.getByRole("button", { name: "Completo" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Guiado" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Rápido" })).toBeInTheDocument();

    // Default mode ("full", empty localStorage) shows the full editor.
    expect(screen.getByTestId("full-editor")).toBeInTheDocument();
    expect(screen.queryByTestId("dynamic-form")).not.toBeInTheDocument();
  });

  it("switches to the guided form (variant='flat')", async () => {
    const user = userEvent.setup();
    render(<GeneratePage />);

    // Pick "Guiado" — the flat form (variant="flat") replaces the editor.
    await user.click(screen.getByRole("button", { name: "Guiado" }));

    const form = screen.getByTestId("dynamic-form");
    expect(form).toBeInTheDocument();
    expect(form).toHaveAttribute("data-variant", "flat");
    expect(screen.queryByTestId("full-editor")).not.toBeInTheDocument();

    // Choice is remembered.
    expect(window.localStorage.getItem(GENERATE_MODE_STORAGE_KEY)).toBe("form");
  });

  it("switches to the quick form (variant='fields')", async () => {
    const user = userEvent.setup();
    render(<GeneratePage />);

    // Pick "Rápido" — the quick form (variant="fields") replaces the editor.
    await user.click(screen.getByRole("button", { name: "Rápido" }));

    const form = screen.getByTestId("dynamic-form");
    expect(form).toBeInTheDocument();
    expect(form).toHaveAttribute("data-variant", "fields");
    expect(screen.queryByTestId("full-editor")).not.toBeInTheDocument();

    // Choice is remembered.
    expect(window.localStorage.getItem(GENERATE_MODE_STORAGE_KEY)).toBe(
      "fields",
    );
  });

  it("disables only 'Completo' and falls back to the guided form when the structure fails to load", () => {
    useTemplateStructureMock.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
    });
    // Even with "full" remembered, an unavailable structure forces a form mode.
    window.localStorage.setItem(GENERATE_MODE_STORAGE_KEY, "full");

    render(<GeneratePage />);

    // "full" is impossible → fall back to the guided flat form.
    expect(screen.getByTestId("dynamic-form")).toHaveAttribute(
      "data-variant",
      "flat",
    );
    expect(screen.queryByTestId("full-editor")).not.toBeInTheDocument();

    // Only "Completo" is disabled; "Guiado" and "Rápido" stay available.
    expect(screen.getByRole("button", { name: "Completo" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Guiado" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Rápido" })).toBeEnabled();
    expect(
      screen.getByText(/no disponible para esta plantilla/i),
    ).toBeInTheDocument();
  });

  it("threads the version's related files into the form modes", async () => {
    // A version with one related file — the form must receive it so its
    // per-field provenance chips can render.
    useTemplateMock.mockReturnValue({
      data: {
        ...template,
        versions: [
          {
            ...template.versions[0],
            files: [
              {
                id: "file-1",
                label: "Anexo A",
                variables: ["nombre"],
                file_size: 1024,
                position: 0,
                created_at: "2026-01-01T00:00:00Z",
              },
            ],
          },
        ],
      },
      isLoading: false,
    });
    const user = userEvent.setup();
    render(<GeneratePage />);

    await user.click(screen.getByRole("button", { name: "Guiado" }));

    expect(screen.getByTestId("dynamic-form")).toHaveAttribute(
      "data-file-count",
      "1",
    );
  });

  it("keeps a remembered 'fields' mode when the structure fails to load", () => {
    useTemplateStructureMock.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
    });
    // A remembered "Rápido" preference survives a structure failure unchanged.
    window.localStorage.setItem(GENERATE_MODE_STORAGE_KEY, "fields");

    render(<GeneratePage />);

    expect(screen.getByTestId("dynamic-form")).toHaveAttribute(
      "data-variant",
      "fields",
    );
    expect(screen.getByRole("button", { name: "Completo" })).toBeDisabled();
  });
});
