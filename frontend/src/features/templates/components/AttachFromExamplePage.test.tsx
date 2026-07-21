import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { AttachFromExamplePage } from "./AttachFromExamplePage";
import { apiClient } from "@/shared/lib/api-client";
import type { Template, TemplateStructure } from "../api/queries";

vi.mock("@/shared/lib/api-client", () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
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

const navigateMock = vi.fn();
vi.mock("@tanstack/react-router", () => ({
  useNavigate: () => navigateMock,
  Link: ({
    children,
    ...props
  }: { children: React.ReactNode } & Record<string, unknown>) => (
    <a {...props}>{children}</a>
  ),
}));

// ---------------------------------------------------------------------------
// Fixtures — template with existing variables "name" (primary) and "monto"
// (contributed by an already-attached related file), plus an example doc
// where "Juan Pérez" (reusable as name) and "100" (new) can be selected.
// ---------------------------------------------------------------------------

const template: Template = {
  id: "tpl-1",
  name: "Contrato Marco",
  description: null,
  current_version: 1,
  variables: ["name", "monto"],
  versions: [
    {
      id: "ver-1",
      version: 1,
      variables: ["name", "monto"],
      variables_meta: [
        { name: "name", contexts: [] },
        { name: "monto", contexts: [] },
      ],
      file_size: 2048,
      created_at: "2026-01-01T00:00:00Z",
      files: [
        {
          id: "file-1",
          label: "Recibo anterior",
          variables: ["monto"],
          file_size: 512,
          position: 0,
          created_at: "2026-01-02T00:00:00Z",
        },
      ],
    },
  ],
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
  access_type: "owned",
  is_owner: true,
  shared_by_email: null,
  owner_name: null,
  folder_id: null,
};

const structure: TemplateStructure = {
  headers: [],
  body: [
    {
      kind: "paragraph",
      level: 0,
      spans: [
        { text: "Recibo emitido a Juan Pérez por 100 Bs.", variable: null },
      ],
      rows: [],
    },
  ],
  footers: [],
};

const DOCX_MIME =
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document";

function makeExampleFile(name = "recibo.docx"): File {
  return new File(["example-bytes"], name, { type: DOCX_MIME });
}

function renderPage(templateOverride: Template = template) {
  vi.mocked(apiClient.get).mockResolvedValue({ data: templateOverride });
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <AttachFromExamplePage templateId="tpl-1" />
    </QueryClientProvider>,
  );
}

/** Upload the example file through the dropzone's hidden input and wait for
 * the analyzed structure to render. */
async function uploadAndAnalyze(container: HTMLElement) {
  const user = userEvent.setup();
  await waitFor(() =>
    expect(
      container.querySelector<HTMLInputElement>('input[type="file"]'),
    ).not.toBeNull(),
  );
  const input = container.querySelector<HTMLInputElement>(
    'input[type="file"]',
  );
  await user.upload(input!, makeExampleFile());
  await waitFor(() =>
    expect(
      screen.getByText("Recibo emitido a Juan Pérez por 100 Bs."),
    ).toBeInTheDocument(),
  );
  return user;
}

/** Fake a mouse text selection fully inside one paragraph (same technique as
 * CreateFromExamplePage.test.tsx — jsdom's Selection is too limited). */
function selectText(anchorNode: Node, text: string) {
  const selection = {
    anchorNode,
    focusNode: anchorNode,
    isCollapsed: false,
    rangeCount: 1,
    toString: () => text,
    getRangeAt: () => ({
      getBoundingClientRect: () => new DOMRect(0, 0, 120, 16),
    }),
    removeAllRanges: vi.fn(),
  } as unknown as Selection;
  vi.spyOn(window, "getSelection").mockReturnValue(selection);
  fireEvent.mouseUp(screen.getByTestId("example-document-surface"));
}

function bodyParagraphNode(): Node {
  return screen.getByText("Recibo emitido a Juan Pérez por 100 Bs.")
    .firstChild!;
}

beforeEach(() => {
  vi.mocked(apiClient.get).mockReset();
  vi.mocked(apiClient.post).mockReset();
  vi.mocked(apiClient.post).mockImplementation(async (url: string) => {
    if (url === "/templates/analyze-example") {
      return { data: { structure } };
    }
    throw new Error(`unexpected POST ${url}`);
  });
  toastSuccessMock.mockClear();
  toastErrorMock.mockClear();
  navigateMock.mockClear();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("AttachFromExamplePage — guard", () => {
  it("blocks users who are neither owner nor admin", async () => {
    renderPage({
      ...template,
      is_owner: false,
      access_type: "shared",
    });

    expect(
      await screen.findByText(/no tiene permisos/i),
    ).toBeInTheDocument();
    expect(screen.queryByText(/arrastre y suelte/i)).not.toBeInTheDocument();
  });
});

describe("AttachFromExamplePage — variable reuse popover", () => {
  it("lists the template's existing variables with their source and fills the input on click", async () => {
    const { container } = renderPage();
    const user = await uploadAndAnalyze(container);

    selectText(bodyParagraphNode(), "Juan Pérez");

    const popover = screen.getByRole("dialog", {
      name: "Convertir en variable",
    });
    expect(
      within(popover).getByText("Variables existentes"),
    ).toBeInTheDocument();

    // Both union variables listed, annotated per source
    const nameOption = within(popover).getByTitle(
      "Usar variable existente name",
    );
    expect(nameOption).toBeInTheDocument();
    expect(within(nameOption).getByText("Documento principal")).toBeInTheDocument();
    const montoOption = within(popover).getByTitle(
      "Usar variable existente monto",
    );
    expect(within(montoOption).getByText("Recibo anterior")).toBeInTheDocument();

    // Clicking a suggestion fills the input and flags it as existing
    await user.click(nameOption);
    expect(
      within(popover).getByLabelText("Nombre de la variable"),
    ).toHaveValue("name");
    expect(
      within(popover).getByText(/variable existente — reutiliza/i),
    ).toBeInTheDocument();
  });

  it("shows the amber nueva indicator for a name the template does not have", async () => {
    const { container } = renderPage();
    const user = await uploadAndAnalyze(container);

    selectText(bodyParagraphNode(), "100");
    const popover = screen.getByRole("dialog", {
      name: "Convertir en variable",
    });

    // Auto-suggested name for "100" is var_100 — not an existing variable
    expect(
      within(popover).getByLabelText("Nombre de la variable"),
    ).toHaveValue("var_100");
    expect(
      within(popover).getByText(/variable nueva — se pedirá al generar/i),
    ).toBeInTheDocument();

    // Typing an existing name flips the indicator
    const input = within(popover).getByLabelText("Nombre de la variable");
    await user.clear(input);
    await user.type(input, "monto");
    expect(
      within(popover).getByText(/variable existente — reutiliza/i),
    ).toBeInTheDocument();
  });
});

describe("AttachFromExamplePage — sidebar", () => {
  it("marks each mapping as existente or nueva and summarizes the new-variable count", async () => {
    const { container } = renderPage();
    const user = await uploadAndAnalyze(container);

    // Mapping 1 — reuse "name" via the suggestion list
    selectText(bodyParagraphNode(), "Juan Pérez");
    await user.click(screen.getByTitle("Usar variable existente name"));
    await user.click(
      screen.getByRole("button", { name: "Convertir en variable" }),
    );

    // Mapping 2 — keep the suggested new name (var_100). Anchor from inside
    // the paragraph, which is now fragmented by the first highlight.
    const mark = container.querySelector('mark[data-variable="name"]')!;
    selectText(mark.firstChild!, "100");
    await user.click(
      screen.getByRole("button", { name: "Convertir en variable" }),
    );

    // Sidebar rows carry the classification chips
    expect(screen.getByText("Existente")).toBeInTheDocument();
    expect(screen.getByText("Nueva")).toBeInTheDocument();

    // Summary line for the extra fill-in step at generation time
    expect(
      screen.getByText(/este documento agrega 1 variable nueva/i),
    ).toBeInTheDocument();
  });
});

describe("AttachFromExamplePage — submit", () => {
  async function addMappings(container: HTMLElement) {
    const user = await uploadAndAnalyze(container);
    selectText(bodyParagraphNode(), "Juan Pérez");
    await user.click(screen.getByTitle("Usar variable existente name"));
    await user.click(
      screen.getByRole("button", { name: "Convertir en variable" }),
    );
    return user;
  }

  it("posts FormData with label + mappings JSON and navigates to the Versiones tab", async () => {
    vi.mocked(apiClient.post).mockImplementation(async (url: string) => {
      if (url === "/templates/analyze-example") {
        return { data: { structure } };
      }
      if (url === "/templates/tpl-1/versions/ver-1/files/from-example") {
        return {
          data: {
            id: "file-9",
            label: "Recibo de pago",
            variables: ["name"],
            file_size: 128,
            position: 1,
            created_at: "2026-07-21T00:00:00Z",
          },
        };
      }
      throw new Error(`unexpected POST ${url}`);
    });

    const { container } = renderPage();
    const user = await addMappings(container);

    await user.type(screen.getByLabelText(/etiqueta/i), "Recibo de pago");
    await user.click(
      screen.getByRole("button", { name: /adjuntar documento/i }),
    );

    await waitFor(() =>
      expect(apiClient.post).toHaveBeenCalledWith(
        "/templates/tpl-1/versions/ver-1/files/from-example",
        expect.any(FormData),
        { headers: { "Content-Type": "multipart/form-data" } },
      ),
    );

    const call = vi
      .mocked(apiClient.post)
      .mock.calls.find(
        ([url]) => url === "/templates/tpl-1/versions/ver-1/files/from-example",
      )!;
    const formData = call[1] as FormData;
    expect(formData.get("label")).toBe("Recibo de pago");
    expect(formData.get("file")).toBeInstanceOf(File);
    expect((formData.get("file") as File).name).toBe("recibo.docx");
    expect(JSON.parse(formData.get("mappings") as string)).toEqual([
      { text: "Juan Pérez", variable: "name" },
    ]);

    expect(toastSuccessMock).toHaveBeenCalledWith(
      "Documento relacionado agregado",
    );
    expect(navigateMock).toHaveBeenCalledWith({
      to: "/templates/$templateId",
      params: { templateId: "tpl-1" },
      search: { tab: "versions" },
    });
  });

  it("renders a 409 duplicate-label detail inline and stays on the page", async () => {
    vi.mocked(apiClient.post).mockImplementation(async (url: string) => {
      if (url === "/templates/analyze-example") {
        return { data: { structure } };
      }
      throw {
        response: {
          status: 409,
          data: {
            detail:
              "Ya existe un archivo relacionado con la etiqueta 'Recibo de pago' en esta versión. Use una etiqueta diferente.",
          },
        },
      };
    });

    const { container } = renderPage();
    const user = await addMappings(container);

    await user.type(screen.getByLabelText(/etiqueta/i), "Recibo de pago");
    await user.click(
      screen.getByRole("button", { name: /adjuntar documento/i }),
    );

    expect(
      await screen.findByText(/ya existe un archivo relacionado/i),
    ).toBeInTheDocument();
    expect(toastErrorMock).toHaveBeenCalled();
    expect(navigateMock).not.toHaveBeenCalled();
  });
});
