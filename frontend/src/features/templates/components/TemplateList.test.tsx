import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { TemplateList } from "./TemplateList";
import { apiClient } from "@/shared/lib/api-client";
import type { Template } from "../api/queries";

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
};

function mockTemplatesResponse(items: Template[], total: number) {
  vi.mocked(apiClient.get).mockResolvedValue({
    data: { items, total, page: 1, size: 20 },
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
