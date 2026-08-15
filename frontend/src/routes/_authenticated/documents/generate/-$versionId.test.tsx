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
  DynamicForm: (props: { variant?: string }) => (
    <div data-testid="dynamic-form" data-variant={props.variant} />
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
  it("defaults to the full document editor and switches to the flat form", async () => {
    const user = userEvent.setup();
    render(<GeneratePage />);

    // Default mode ("full", empty localStorage) shows the full editor.
    expect(screen.getByTestId("full-editor")).toBeInTheDocument();
    expect(screen.queryByTestId("dynamic-form")).not.toBeInTheDocument();

    // Pick "Formulario" — the flat form (variant="flat") replaces the editor.
    await user.click(screen.getByRole("button", { name: "Formulario" }));

    const form = screen.getByTestId("dynamic-form");
    expect(form).toBeInTheDocument();
    expect(form).toHaveAttribute("data-variant", "flat");
    expect(screen.queryByTestId("full-editor")).not.toBeInTheDocument();

    // Choice is remembered.
    expect(window.localStorage.getItem(GENERATE_MODE_STORAGE_KEY)).toBe("form");
  });

  it("forces the form and disables the full option when the structure fails to load", () => {
    useTemplateStructureMock.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
    });
    // Even with "full" remembered, an unavailable structure forces the form.
    window.localStorage.setItem(GENERATE_MODE_STORAGE_KEY, "full");

    render(<GeneratePage />);

    expect(screen.getByTestId("dynamic-form")).toHaveAttribute(
      "data-variant",
      "flat",
    );
    expect(screen.queryByTestId("full-editor")).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Documento completo" }),
    ).toBeDisabled();
    expect(
      screen.getByText(/no disponible para esta plantilla/i),
    ).toBeInTheDocument();
  });
});
