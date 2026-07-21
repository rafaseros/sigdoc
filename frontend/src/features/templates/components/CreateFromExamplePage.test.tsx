import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { CreateFromExamplePage } from "./CreateFromExamplePage";
import { apiClient } from "@/shared/lib/api-client";
import type { TemplateStructure } from "../api/queries";

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
// Fixture — "Juan Pérez" appears 4 times: twice in a body paragraph, once in
// a bullet item and once inside a table cell. Headers/footers carry the
// company name.
// ---------------------------------------------------------------------------

const structure: TemplateStructure = {
  headers: [
    {
      kind: "paragraph",
      level: 0,
      spans: [{ text: "ACME S.R.L.", variable: null }],
      rows: [],
    },
  ],
  body: [
    {
      kind: "heading",
      level: 1,
      spans: [{ text: "Contrato de servicios", variable: null }],
      rows: [],
    },
    {
      kind: "paragraph",
      level: 0,
      spans: [
        {
          text: "Entre ACME S.R.L. y Juan Pérez, el trabajador Juan Pérez acepta.",
          variable: null,
        },
      ],
      rows: [],
    },
    {
      kind: "list_bullet",
      level: 1,
      spans: [{ text: "Firma: Juan Pérez", variable: null }],
      rows: [],
    },
    {
      kind: "table",
      level: 0,
      spans: [],
      rows: [
        {
          cells: [
            {
              nodes: [
                {
                  kind: "paragraph",
                  level: 0,
                  spans: [{ text: "Cliente: Juan Pérez", variable: null }],
                  rows: [],
                },
              ],
            },
          ],
        },
      ],
    },
  ],
  footers: [
    {
      kind: "paragraph",
      level: 0,
      spans: [{ text: "Documento emitido por ACME S.R.L.", variable: null }],
      rows: [],
    },
  ],
};

const DOCX_MIME =
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document";

function makeExampleFile(name = "contrato.docx"): File {
  return new File(["example-bytes"], name, { type: DOCX_MIME });
}

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <CreateFromExamplePage />
    </QueryClientProvider>,
  );
}

/** Upload the example file through the dropzone's hidden input and wait for
 * the analyzed structure to render. */
async function uploadAndAnalyze(container: HTMLElement) {
  const user = userEvent.setup();
  const input = container.querySelector<HTMLInputElement>(
    'input[type="file"]',
  );
  expect(input).not.toBeNull();
  await user.upload(input!, makeExampleFile());
  await waitFor(() =>
    expect(screen.getByText("Contrato de servicios")).toBeInTheDocument(),
  );
  return user;
}

/**
 * Fake a mouse text selection fully inside one paragraph. jsdom's real
 * window.getSelection is too limited, so the Selection object is stubbed
 * with real DOM nodes as anchor/focus; the selection math itself is covered
 * by the fromExample lib tests.
 */
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
  return screen.getByText(
    "Entre ACME S.R.L. y Juan Pérez, el trabajador Juan Pérez acepta.",
  ).firstChild!;
}

beforeEach(() => {
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

describe("CreateFromExamplePage — analyze step", () => {
  it("analyzes the uploaded file and renders the read-only structure", async () => {
    const { container } = renderPage();
    await uploadAndAnalyze(container);

    expect(apiClient.post).toHaveBeenCalledWith(
      "/templates/analyze-example",
      expect.any(FormData),
      { headers: { "Content-Type": "multipart/form-data" } },
    );

    // Sections
    expect(screen.getByText("Encabezado")).toBeInTheDocument();
    expect(screen.getByText("Contenido")).toBeInTheDocument();
    expect(screen.getByText("Pie de página")).toBeInTheDocument();

    // Header, list, table cell and footer content
    expect(screen.getByText("ACME S.R.L.")).toBeInTheDocument();
    expect(screen.getByText("Firma: Juan Pérez")).toBeInTheDocument();
    expect(screen.getByText("Cliente: Juan Pérez")).toBeInTheDocument();
    expect(
      screen.getByText("Documento emitido por ACME S.R.L."),
    ).toBeInTheDocument();

    // Teaching hint shows before any mapping
    expect(
      screen.getByText(/Seleccione con el mouse el texto/),
    ).toBeInTheDocument();

    // CTA disabled with zero mappings
    expect(
      screen.getByRole("button", { name: /crear plantilla/i }),
    ).toBeDisabled();
  });

  it("shows the backend detail in an error banner when analysis fails", async () => {
    vi.mocked(apiClient.post).mockRejectedValueOnce({
      response: { status: 400, data: { detail: "El archivo está vacío" } },
    });
    const { container } = renderPage();
    const user = userEvent.setup();
    const input = container.querySelector<HTMLInputElement>(
      'input[type="file"]',
    );
    await user.upload(input!, makeExampleFile());

    expect(
      await screen.findByText("El archivo está vacío"),
    ).toBeInTheDocument();
    // Back on the dropzone step
    expect(
      screen.getByText(/arrastre y suelte un documento/i),
    ).toBeInTheDocument();
  });
});

describe("CreateFromExamplePage — marking variables", () => {
  it("opens the popover on a valid selection and adds a mapping with highlights everywhere", async () => {
    const { container } = renderPage();
    const user = await uploadAndAnalyze(container);

    selectText(bodyParagraphNode(), "Juan Pérez");

    const popover = screen.getByRole("dialog", {
      name: "Convertir en variable",
    });
    expect(within(popover).getByText("«Juan Pérez»")).toBeInTheDocument();
    expect(
      within(popover).getByText("4 apariciones en el documento"),
    ).toBeInTheDocument();

    // Auto-suggested snake_case name
    const nameInput = within(popover).getByLabelText("Nombre de la variable");
    expect(nameInput).toHaveValue("juan_perez");

    await user.click(
      within(popover).getByRole("button", { name: "Convertir en variable" }),
    );

    // Popover closes, sidebar lists the mapping with its occurrence count
    expect(
      screen.queryByRole("dialog", { name: "Convertir en variable" }),
    ).not.toBeInTheDocument();
    expect(screen.getByText("{{ juan_perez }}")).toBeInTheDocument();
    expect(screen.getByText("«Juan Pérez»")).toBeInTheDocument();
    expect(screen.getByText("×4")).toBeInTheDocument();

    // Every exact occurrence is highlighted, with the variable in the title
    const marks = container.querySelectorAll(
      'mark[data-variable="juan_perez"]',
    );
    expect(marks).toHaveLength(4);
    for (const mark of marks) {
      expect(mark).toHaveAttribute("title", "{{ juan_perez }}");
      expect(mark.textContent).toBe("Juan Pérez");
    }

    // Teaching hint is gone once a mapping exists
    expect(
      screen.queryByText(/Seleccione con el mouse el texto/),
    ).not.toBeInTheDocument();
  });

  it("validates the variable name live and disables the confirm button", async () => {
    const { container } = renderPage();
    const user = await uploadAndAnalyze(container);

    selectText(bodyParagraphNode(), "Juan Pérez");
    const popover = screen.getByRole("dialog", {
      name: "Convertir en variable",
    });
    const nameInput = within(popover).getByLabelText("Nombre de la variable");
    const confirm = within(popover).getByRole("button", {
      name: "Convertir en variable",
    });

    await user.clear(nameInput);
    await user.type(nameInput, "Nombre Inválido");
    expect(confirm).toBeDisabled();

    await user.clear(nameInput);
    await user.type(nameInput, "nombre_valido");
    expect(confirm).toBeEnabled();
  });

  it("blocks adding a mapping whose exact text already exists, with a toast", async () => {
    const { container } = renderPage();
    const user = await uploadAndAnalyze(container);

    // First mapping
    selectText(bodyParagraphNode(), "Juan Pérez");
    await user.click(
      screen.getByRole("button", { name: "Convertir en variable" }),
    );
    expect(screen.getByText("{{ juan_perez }}")).toBeInTheDocument();

    // Second selection of the same exact text (from inside a highlight)
    const mark = container.querySelector('mark[data-variable="juan_perez"]')!;
    selectText(mark.firstChild!, "Juan Pérez");
    await user.click(
      screen.getByRole("button", { name: "Convertir en variable" }),
    );

    expect(toastErrorMock).toHaveBeenCalledWith(
      "Ese texto ya está convertido en variable.",
    );
    // Still a single mapping in the sidebar
    expect(screen.getAllByText("{{ juan_perez }}")).toHaveLength(1);
  });

  it("blocks converting text whose every occurrence is consumed by an existing longer mapping", async () => {
    const { container } = renderPage();
    const user = await uploadAndAnalyze(container);

    // Map the long text first — consumes every "Juan" in the document
    selectText(bodyParagraphNode(), "Juan Pérez");
    await user.click(
      screen.getByRole("button", { name: "Convertir en variable" }),
    );
    expect(screen.getByText("{{ juan_perez }}")).toBeInTheDocument();

    // Selecting the contained "Juan" opens the popover in blocked mode:
    // hint shown, no confirm form.
    const mark = container.querySelector('mark[data-variable="juan_perez"]')!;
    selectText(mark.firstChild!, "Juan");

    const popover = screen.getByRole("dialog", {
      name: "Convertir en variable",
    });
    expect(
      within(popover).getByText(/ya están dentro de una variable/i),
    ).toBeInTheDocument();
    expect(
      within(popover).queryByRole("button", { name: "Convertir en variable" }),
    ).not.toBeInTheDocument();
    // No second mapping was added
    expect(screen.queryByText("{{ juan }}")).not.toBeInTheDocument();
  });

  it("blocks a longer mapping that would leave an existing variable without occurrences", async () => {
    const { container } = renderPage();
    const user = await uploadAndAnalyze(container);

    // Map the short text first — 4 effective occurrences
    selectText(bodyParagraphNode(), "Juan");
    await user.click(
      screen.getByRole("button", { name: "Convertir en variable" }),
    );
    expect(screen.getByText("{{ juan }}")).toBeInTheDocument();
    expect(screen.getByText("×4")).toBeInTheDocument();

    // The longer text would consume every "Juan" → existing mapping drops
    // to 0. Anchor from inside a highlight — the paragraph text is now
    // fragmented by <mark> elements.
    const mark = container.querySelector('mark[data-variable="juan"]')!;
    selectText(mark.firstChild!, "Juan Pérez");
    await user.click(
      screen.getByRole("button", { name: "Convertir en variable" }),
    );

    expect(toastErrorMock).toHaveBeenCalledWith(
      expect.stringContaining("juan"),
    );
    // The longer mapping was NOT added; the original stays
    expect(screen.queryByText("{{ juan_perez }}")).not.toBeInTheDocument();
    expect(screen.getByText("{{ juan }}")).toBeInTheDocument();
  });

  it("removes a mapping and its highlights from the sidebar", async () => {
    const { container } = renderPage();
    const user = await uploadAndAnalyze(container);

    selectText(bodyParagraphNode(), "Juan Pérez");
    await user.click(
      screen.getByRole("button", { name: "Convertir en variable" }),
    );
    expect(
      container.querySelectorAll('mark[data-variable="juan_perez"]'),
    ).toHaveLength(4);

    await user.click(
      screen.getByRole("button", { name: "Quitar variable juan_perez" }),
    );

    expect(screen.queryByText("{{ juan_perez }}")).not.toBeInTheDocument();
    expect(
      container.querySelectorAll('mark[data-variable="juan_perez"]'),
    ).toHaveLength(0);
  });
});

describe("CreateFromExamplePage — submit", () => {
  async function addJuanPerezMapping(container: HTMLElement) {
    const user = await uploadAndAnalyze(container);
    selectText(bodyParagraphNode(), "Juan Pérez");
    await user.click(
      screen.getByRole("button", { name: "Convertir en variable" }),
    );
    return user;
  }

  it("submits FormData with the mappings JSON string and navigates on 201", async () => {
    vi.mocked(apiClient.post).mockImplementation(async (url: string) => {
      if (url === "/templates/analyze-example") {
        return { data: { structure } };
      }
      if (url === "/templates/from-example") {
        return {
          data: {
            id: "tpl-9",
            name: "Contrato Base",
            description: null,
            version: 1,
            variables: ["juan_perez"],
            created_at: "2026-07-21T00:00:00Z",
          },
        };
      }
      throw new Error(`unexpected POST ${url}`);
    });

    const { container } = renderPage();
    const user = await addJuanPerezMapping(container);

    const nameInput = screen.getByLabelText(/nombre \*/i);
    await user.clear(nameInput);
    await user.type(nameInput, "Contrato Base");

    await user.click(screen.getByRole("button", { name: /crear plantilla/i }));

    await waitFor(() =>
      expect(apiClient.post).toHaveBeenCalledWith(
        "/templates/from-example",
        expect.any(FormData),
        { headers: { "Content-Type": "multipart/form-data" } },
      ),
    );

    const call = vi
      .mocked(apiClient.post)
      .mock.calls.find(([url]) => url === "/templates/from-example")!;
    const formData = call[1] as FormData;
    expect(formData.get("name")).toBe("Contrato Base");
    expect(formData.get("description")).toBeNull();
    expect(formData.get("file")).toBeInstanceOf(File);
    expect((formData.get("file") as File).name).toBe("contrato.docx");
    expect(JSON.parse(formData.get("mappings") as string)).toEqual([
      { text: "Juan Pérez", variable: "juan_perez" },
    ]);

    expect(toastSuccessMock).toHaveBeenCalledWith(
      "Plantilla «Contrato Base» creada con éxito",
    );
    expect(navigateMock).toHaveBeenCalledWith({
      to: "/templates/$templateId",
      params: { templateId: "tpl-9" },
    });
  });

  it("lists the missing texts from a 422 missing_texts response", async () => {
    vi.mocked(apiClient.post).mockImplementation(async (url: string) => {
      if (url === "/templates/analyze-example") {
        return { data: { structure } };
      }
      throw {
        response: {
          status: 422,
          data: {
            detail: {
              message: "Textos no encontrados en el documento",
              missing_texts: ["Juan Pérez", "ACME"],
            },
          },
        },
      };
    });

    const { container } = renderPage();
    const user = await addJuanPerezMapping(container);

    await user.click(screen.getByRole("button", { name: /crear plantilla/i }));

    expect(
      await screen.findByText("Textos no encontrados en el documento"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Juan Pérez", { selector: "li" }),
    ).toBeInTheDocument();
    expect(screen.getByText("ACME", { selector: "li" })).toBeInTheDocument();
    expect(toastErrorMock).toHaveBeenCalledWith(
      "Textos no encontrados en el documento",
    );
    expect(navigateMock).not.toHaveBeenCalled();
  });

  it("shows a string 409 detail as the error message", async () => {
    vi.mocked(apiClient.post).mockImplementation(async (url: string) => {
      if (url === "/templates/analyze-example") {
        return { data: { structure } };
      }
      throw {
        response: {
          status: 409,
          data: { detail: "Ya existe una plantilla con ese nombre" },
        },
      };
    });

    const { container } = renderPage();
    const user = await addJuanPerezMapping(container);

    await user.click(screen.getByRole("button", { name: /crear plantilla/i }));

    expect(
      await screen.findByText("Ya existe una plantilla con ese nombre"),
    ).toBeInTheDocument();
    expect(toastErrorMock).toHaveBeenCalledWith(
      "Ya existe una plantilla con ese nombre",
    );
  });
});
