import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { TemplateList } from "./TemplateList";
import { apiClient } from "@/shared/lib/api-client";
import type { Template } from "../api/queries";
import type { Folder } from "../api/folders";

vi.mock("@/shared/lib/api-client", () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}));

vi.mock("@tanstack/react-router", () => ({
  useNavigate: () => vi.fn(),
}));

const VIEW_MODE_KEY = "templates:view-mode";

const ownedTemplate: Template = {
  id: "template-owned",
  name: "Contrato de Servicios",
  description: "Plantilla estándar de contrato",
  current_version: 2,
  variables: ["cliente", "fecha", "monto"],
  versions: [],
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-02-15T00:00:00Z",
  access_type: "owned",
  is_owner: true,
  shared_by_email: null,
  owner_name: "Ana Gómez",
  folder_id: null,
};

const sharedTemplate: Template = {
  id: "template-shared",
  name: "Informe Mensual",
  description: "Plantilla compartida por el equipo",
  current_version: 1,
  variables: ["periodo"],
  versions: [],
  created_at: "2026-01-05T00:00:00Z",
  updated_at: "2026-01-20T00:00:00Z",
  access_type: "shared",
  is_owner: false,
  shared_by_email: "maria@empresa.com",
  owner_name: "María Pérez",
  folder_id: null,
};

/**
 * Mocks `apiClient.get` for BOTH `/templates` and `/folders` in one shot,
 * routing by URL prefix since the sidebar's `useFolders()` and the list's
 * `useTemplates()` share the same mocked function. Folders default to `[]`
 * so pre-existing tests (which don't care about the sidebar) keep working
 * unmodified.
 */
function mockTemplatesResponse(
  items: Template[],
  total: number,
  folders: Folder[] = [],
) {
  vi.mocked(apiClient.get).mockImplementation(async (url: string) => {
    if (typeof url === "string" && url.startsWith("/folders")) {
      return { data: { folders } };
    }
    return { data: { items, total, page: 1, size: 20 } };
  });
}

function renderList() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  const utils = render(
    <QueryClientProvider client={queryClient}>
      <TemplateList />
    </QueryClientProvider>,
  );
  return { ...utils, queryClient };
}

describe("TemplateList — view mode toggle", () => {
  beforeEach(() => {
    vi.mocked(apiClient.get).mockReset();
    window.localStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("switches from cards to table and back, persisting the choice to localStorage", async () => {
    mockTemplatesResponse([ownedTemplate, sharedTemplate], 2);
    const user = userEvent.setup();
    renderList();

    await waitFor(() =>
      expect(screen.getByText("Contrato de Servicios")).toBeInTheDocument(),
    );

    // Default is cards — no table semantics yet.
    expect(screen.queryByRole("table")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /vista de tabla/i }));

    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(window.localStorage.getItem(VIEW_MODE_KEY)).toBe("table");

    await user.click(screen.getByRole("button", { name: /vista de tarjetas/i }));

    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    expect(window.localStorage.getItem(VIEW_MODE_KEY)).toBe("cards");
  });
});

describe("TemplateList — Propietario / owner_name display", () => {
  beforeEach(() => {
    vi.mocked(apiClient.get).mockReset();
    window.localStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows owner_name in the Propietario column in table mode", async () => {
    mockTemplatesResponse([ownedTemplate, sharedTemplate], 2);
    const user = userEvent.setup();
    renderList();

    await waitFor(() =>
      expect(screen.getByText("Contrato de Servicios")).toBeInTheDocument(),
    );
    await user.click(screen.getByRole("button", { name: /vista de tabla/i }));

    expect(screen.getByRole("columnheader", { name: /propietario/i })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "Ana Gómez" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "María Pérez" })).toBeInTheDocument();
  });

  it("shows 'Compartida por {owner_name}' only for shared templates in cards mode", async () => {
    mockTemplatesResponse([ownedTemplate, sharedTemplate], 2);
    renderList();

    await waitFor(() =>
      expect(screen.getByText("Contrato de Servicios")).toBeInTheDocument(),
    );

    expect(
      screen.getByText((content) => content.includes("Compartida por")),
    ).toBeInTheDocument();
    expect(screen.getByText("María Pérez")).toBeInTheDocument();
    // The owned template must NOT get a "Compartida por" line — only one
    // such line should exist across the whole list.
    expect(
      screen.getAllByText((content) => content.includes("Compartida por")),
    ).toHaveLength(1);
  });
});

describe("TemplateList — empty states", () => {
  beforeEach(() => {
    vi.mocked(apiClient.get).mockReset();
    window.localStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows the search-empty (dashed) variant when a search yields no results", async () => {
    mockTemplatesResponse([ownedTemplate, sharedTemplate], 2);
    const user = userEvent.setup();
    renderList();

    await waitFor(() =>
      expect(screen.getByText("Contrato de Servicios")).toBeInTheDocument(),
    );

    mockTemplatesResponse([], 0);
    await user.type(screen.getByPlaceholderText(/buscar plantillas/i), "zzz");

    expect(
      await screen.findByText(
        /no se encontraron plantillas que coincidan con su búsqueda/i,
      ),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(/use el botón/i),
    ).not.toBeInTheDocument();
  });

  it("shows the genuinely-empty (Card + CTA) variant naming the Subir Plantilla button when there are no templates at all", async () => {
    mockTemplatesResponse([], 0);
    renderList();

    expect(
      await screen.findByText(/aún no hay plantillas/i),
    ).toBeInTheDocument();
    const cta = screen.getByText((_, el) => el?.tagName === "STRONG" && el.textContent === "Subir Plantilla");
    expect(cta).toBeInTheDocument();
    expect(
      screen.queryByText(/coincidan con su búsqueda/i),
    ).not.toBeInTheDocument();
  });
});

describe("TemplateList — pagination", () => {
  beforeEach(() => {
    vi.mocked(apiClient.get).mockReset();
    window.localStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the pager and requests page 2 when total exceeds the page size", async () => {
    mockTemplatesResponse([ownedTemplate, sharedTemplate], 45);
    const user = userEvent.setup();
    renderList();

    await waitFor(() =>
      expect(screen.getByText("Contrato de Servicios")).toBeInTheDocument(),
    );

    expect(screen.getByText("Página 1 de 3")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /siguiente/i }));

    await waitFor(() =>
      expect(apiClient.get).toHaveBeenCalledWith(
        expect.stringContaining("page=2"),
      ),
    );
  });

  it("hides the pager when total does not exceed the page size", async () => {
    mockTemplatesResponse([ownedTemplate, sharedTemplate], 2);
    renderList();

    await waitFor(() =>
      expect(screen.getByText("Contrato de Servicios")).toBeInTheDocument(),
    );

    expect(screen.queryByText(/página \d+ de \d+/i)).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /siguiente/i }),
    ).not.toBeInTheDocument();
  });
});

describe("TemplateList — page reset on search", () => {
  beforeEach(() => {
    vi.mocked(apiClient.get).mockReset();
    window.localStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("resets to page 1 when the user searches while on page 2 (regression guard for the page-reset effect)", async () => {
    mockTemplatesResponse([ownedTemplate, sharedTemplate], 45);
    const user = userEvent.setup();
    renderList();

    await waitFor(() =>
      expect(screen.getByText("Contrato de Servicios")).toBeInTheDocument(),
    );

    await user.click(screen.getByRole("button", { name: /siguiente/i }));
    await waitFor(() =>
      expect(apiClient.get).toHaveBeenCalledWith(
        expect.stringContaining("page=2"),
      ),
    );

    vi.mocked(apiClient.get).mockClear();

    await user.type(screen.getByPlaceholderText(/buscar plantillas/i), "acta");

    // The 300ms debounce must elapse before the search takes effect — wait
    // for the resulting request instead of asserting immediately. If the
    // page-reset effect were removed, this call would carry page=2 instead.
    await waitFor(
      () => {
        const calls = vi.mocked(apiClient.get).mock.calls;
        const lastCall = calls[calls.length - 1]?.[0] as string | undefined;
        expect(lastCall).toContain("search=acta");
        expect(lastCall).toContain("page=1");
      },
      { timeout: 2000 },
    );
  });
});

describe("TemplateList — page clamp when total shrinks", () => {
  beforeEach(() => {
    vi.mocked(apiClient.get).mockReset();
    window.localStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("clamps back to the last valid page when a refetch reports a shrunken total", async () => {
    let total = 100; // 5 pages at PAGE_SIZE=20
    vi.mocked(apiClient.get).mockImplementation(async () => ({
      data: { items: [ownedTemplate, sharedTemplate], total, page: 1, size: 20 },
    }));

    const user = userEvent.setup();
    const { queryClient } = renderList();

    await waitFor(() =>
      expect(screen.getByText("Contrato de Servicios")).toBeInTheDocument(),
    );

    // Navigate to page 3.
    await user.click(screen.getByRole("button", { name: /siguiente/i }));
    await waitFor(() =>
      expect(apiClient.get).toHaveBeenCalledWith(
        expect.stringContaining("page=2"),
      ),
    );
    await user.click(screen.getByRole("button", { name: /siguiente/i }));
    await waitFor(() =>
      expect(apiClient.get).toHaveBeenCalledWith(
        expect.stringContaining("page=3"),
      ),
    );
    await waitFor(() =>
      expect(screen.getByText("Página 3 de 5")).toBeInTheDocument(),
    );

    // Simulate an external delete/invalidation shrinking the total while
    // we're stranded on page 3 — only 2 pages' worth of data remain.
    total = 25;
    await queryClient.invalidateQueries();

    await waitFor(
      () => {
        expect(screen.getByText("Página 2 de 2")).toBeInTheDocument();
        const calls = vi.mocked(apiClient.get).mock.calls;
        const lastCall = calls[calls.length - 1]?.[0] as string | undefined;
        expect(lastCall).toContain("page=2");
      },
      { timeout: 2000 },
    );
  });
});

describe("TemplateList — folder sidebar", () => {
  const folders: Folder[] = [
    { id: "folder-1", name: "Contratos", template_count: 7 },
    { id: "folder-2", name: "Informes", template_count: 12 },
  ];

  beforeEach(() => {
    vi.mocked(apiClient.get).mockReset();
    vi.mocked(apiClient.post).mockReset();
    vi.mocked(apiClient.delete).mockReset();
    window.localStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders folder rows with their counts; clicking one filters by folder_id and resets to page 1", async () => {
    mockTemplatesResponse([ownedTemplate, sharedTemplate], 45, folders);
    const user = userEvent.setup();
    renderList();

    await waitFor(() => expect(screen.getByText("Contratos")).toBeInTheDocument());
    expect(screen.getByText("Informes")).toBeInTheDocument();
    expect(screen.getByText("7")).toBeInTheDocument();
    expect(screen.getByText("12")).toBeInTheDocument();

    // Move off page 1 first so we can prove the folder click resets it.
    await waitFor(() =>
      expect(screen.getByText("Página 1 de 3")).toBeInTheDocument(),
    );
    await user.click(screen.getByRole("button", { name: /siguiente/i }));
    await waitFor(() =>
      expect(apiClient.get).toHaveBeenCalledWith(
        expect.stringContaining("page=2"),
      ),
    );

    vi.mocked(apiClient.get).mockClear();
    await user.click(screen.getByRole("button", { name: "Contratos" }));

    await waitFor(() =>
      expect(apiClient.get).toHaveBeenCalledWith(
        expect.stringMatching(/\/templates\?.*folder_id=folder-1/),
      ),
    );
    const lastCalls = vi.mocked(apiClient.get).mock.calls;
    const lastTemplatesCall = lastCalls
      .map((c) => c[0] as string)
      .filter((url) => url.startsWith("/templates"))
      .pop();
    expect(lastTemplatesCall).toContain("page=1");
  });

  it('sends folder_id="none" when "Sin carpeta" is selected', async () => {
    mockTemplatesResponse([ownedTemplate, sharedTemplate], 2, folders);
    const user = userEvent.setup();
    renderList();

    await waitFor(() =>
      expect(screen.getByText("Contrato de Servicios")).toBeInTheDocument(),
    );
    vi.mocked(apiClient.get).mockClear();

    await user.click(screen.getByRole("button", { name: "Sin carpeta" }));

    await waitFor(() =>
      expect(apiClient.get).toHaveBeenCalledWith(
        expect.stringMatching(/\/templates\?.*folder_id=none/),
      ),
    );
  });

  it("shows the teaching copy when there are no folders yet", async () => {
    mockTemplatesResponse([ownedTemplate, sharedTemplate], 2, []);
    renderList();

    expect(
      await screen.findByText(/cree carpetas para organizar sus plantillas/i),
    ).toBeInTheDocument();
  });

  it("hides the teaching copy once at least one folder exists", async () => {
    mockTemplatesResponse([ownedTemplate, sharedTemplate], 2, folders);
    renderList();

    await waitFor(() => expect(screen.getByText("Contratos")).toBeInTheDocument());
    expect(
      screen.queryByText(/cree carpetas para organizar sus plantillas/i),
    ).not.toBeInTheDocument();
  });
});

describe("TemplateList — create folder", () => {
  beforeEach(() => {
    vi.mocked(apiClient.get).mockReset();
    vi.mocked(apiClient.post).mockReset();
    window.localStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("creates a new folder via POST and refetches the folder list", async () => {
    mockTemplatesResponse([ownedTemplate, sharedTemplate], 2, []);
    vi.mocked(apiClient.post).mockResolvedValue({
      data: { id: "folder-3", name: "Nueva", template_count: 0 },
    });
    const user = userEvent.setup();
    renderList();

    await waitFor(() =>
      expect(screen.getByText("Contrato de Servicios")).toBeInTheDocument(),
    );

    await user.click(screen.getByRole("button", { name: /nueva carpeta/i }));
    const nameInput = await screen.findByLabelText(/nombre de la carpeta/i);
    await user.type(nameInput, "Nueva");

    vi.mocked(apiClient.get).mockClear();
    await user.click(screen.getByRole("button", { name: /crear carpeta/i }));

    await waitFor(() =>
      expect(apiClient.post).toHaveBeenCalledWith("/folders", { name: "Nueva" }),
    );
    // Creating a folder invalidates the folders query — it must refetch.
    await waitFor(() =>
      expect(apiClient.get).toHaveBeenCalledWith(
        expect.stringMatching(/^\/folders/),
      ),
    );
  });
});

describe("TemplateList — delete folder", () => {
  const folders: Folder[] = [
    { id: "folder-1", name: "Contratos", template_count: 7 },
  ];

  beforeEach(() => {
    vi.mocked(apiClient.get).mockReset();
    vi.mocked(apiClient.delete).mockReset();
    window.localStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("confirms that templates are preserved (only unfiled) and sends DELETE", async () => {
    mockTemplatesResponse([ownedTemplate, sharedTemplate], 2, folders);
    vi.mocked(apiClient.delete).mockResolvedValue({ data: undefined });
    const user = userEvent.setup();
    renderList();

    await waitFor(() => expect(screen.getByText("Contratos")).toBeInTheDocument());

    await user.click(
      screen.getByRole("button", { name: "Eliminar carpeta Contratos" }),
    );

    expect(
      await screen.findByText(/las plantillas no se eliminan; quedan sin carpeta/i),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /^eliminar$/i }));

    await waitFor(() =>
      expect(apiClient.delete).toHaveBeenCalledWith("/folders/folder-1"),
    );
  });
});
