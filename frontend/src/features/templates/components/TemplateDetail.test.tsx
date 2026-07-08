import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import TemplateDetail from "./TemplateDetail";
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
  Link: ({
    children,
    ...props
  }: { children: React.ReactNode; to: string } & Record<string, unknown>) => (
    <a {...props}>{children}</a>
  ),
}));

const template: Template = {
  id: "template-1",
  name: "Contrato de Servicios",
  description: "Plantilla estándar",
  current_version: 1,
  variables: ["monto"],
  versions: [
    {
      id: "version-1",
      version: 1,
      variables: ["monto"],
      variables_meta: [{ name: "monto", contexts: [], type: "decimal" }],
      file_size: 1024,
      created_at: "2026-01-01T00:00:00Z",
    },
  ],
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
  access_type: "owned",
  is_owner: true,
  shared_by_email: null,
  owner_name: "Ana Gómez",
  folder_id: null,
};

function mockDetailResponses(templateOverride: Template = template) {
  vi.mocked(apiClient.get).mockImplementation(async (url: string) => {
    if (typeof url === "string" && url.includes("/shares")) {
      return { data: [] };
    }
    if (typeof url === "string" && url.startsWith("/documents")) {
      return { data: { items: [], total: 0, page: 1, size: 1 } };
    }
    if (typeof url === "string" && url.includes("/presets")) {
      return { data: { presets: [] } };
    }
    return { data: templateOverride };
  });
}

function renderDetail() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <TemplateDetail templateId="template-1" />
    </QueryClientProvider>,
  );
}

describe("TemplateDetail — help center mount", () => {
  beforeEach(() => {
    vi.mocked(apiClient.get).mockReset();
    mockDetailResponses();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the Guía button in the action row and opens on 'Subir plantillas' by default", async () => {
    const user = userEvent.setup();
    renderDetail();

    await waitFor(() =>
      expect(screen.getByText("Contrato de Servicios")).toBeInTheDocument(),
    );

    await user.click(screen.getByRole("button", { name: /^guía$/i }));

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(
      screen.getByRole("tab", { name: /subir plantillas/i }),
    ).toHaveAttribute("aria-selected", "true");
  });

  it("opens on 'Variables calculadas' when launched from the Variables tab", async () => {
    const user = userEvent.setup();
    renderDetail();

    await waitFor(() =>
      expect(screen.getByText("Contrato de Servicios")).toBeInTheDocument(),
    );

    await user.click(screen.getByRole("button", { name: /^variables/i }));
    await user.click(screen.getByRole("button", { name: /^guía$/i }));

    expect(
      screen.getByRole("tab", { name: /variables calculadas/i }),
    ).toHaveAttribute("aria-selected", "true");
  });
});

describe("TemplateDetail — action row reorganization", () => {
  beforeEach(() => {
    vi.mocked(apiClient.get).mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("defaults to the Documentos tab and never wraps the action row to a second line", async () => {
    mockDetailResponses();
    renderDetail();

    await waitFor(() =>
      expect(screen.getByText("Contrato de Servicios")).toBeInTheDocument(),
    );

    // "Documentos" content ("Documentos generados") is visible by default —
    // "Información" content ("Información de la plantilla") is not.
    expect(screen.getByText("Documentos generados")).toBeInTheDocument();
    expect(
      screen.queryByText("Información de la plantilla"),
    ).not.toBeInTheDocument();
  });

  it("orders the sidebar nav generation-first, with Información last", async () => {
    mockDetailResponses();
    renderDetail();

    await waitFor(() =>
      expect(screen.getByText("Contrato de Servicios")).toBeInTheDocument(),
    );

    const nav = screen.getByRole("navigation");
    const itemNames = within(nav)
      .getAllByRole("button")
      .map((btn) => btn.textContent);

    expect(itemNames).toEqual([
      expect.stringMatching(/^Documentos/),
      expect.stringMatching(/^Datos guardados/),
      expect.stringMatching(/^Variables/),
      expect.stringMatching(/^Versiones/),
      expect.stringMatching(/^Compartido/),
      expect.stringMatching(/^Información/),
    ]);
  });

  it("collapses owner management actions into the 'Más acciones' menu, with Eliminar destructive and last", async () => {
    mockDetailResponses();
    const user = userEvent.setup();
    renderDetail();

    await waitFor(() =>
      expect(screen.getByText("Contrato de Servicios")).toBeInTheDocument(),
    );

    // Renombrar/Mover/Compartir/Eliminar no longer render as standalone
    // buttons in the action row.
    expect(
      screen.queryByRole("button", { name: /^renombrar$/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /^mover a carpeta$/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /^compartir$/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /^eliminar$/i }),
    ).not.toBeInTheDocument();

    const trigger = screen.getByRole("button", { name: /más acciones/i });
    await user.click(trigger);

    expect(
      await screen.findByRole("menuitem", { name: /renombrar/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("menuitem", { name: /mover a carpeta/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("menuitem", { name: /compartir/i }),
    ).toBeInTheDocument();

    const deleteItem = screen.getByRole("menuitem", { name: /eliminar/i });
    expect(deleteItem).toBeInTheDocument();
    expect(deleteItem).toHaveAttribute("data-variant", "destructive");

    const menuItems = screen.getAllByRole("menuitem");
    expect(menuItems[menuItems.length - 1]).toBe(deleteItem);
  });

  it("opens the rename dialog from the 'Más acciones' menu", async () => {
    mockDetailResponses();
    const user = userEvent.setup();
    renderDetail();

    await waitFor(() =>
      expect(screen.getByText("Contrato de Servicios")).toBeInTheDocument(),
    );

    await user.click(screen.getByRole("button", { name: /más acciones/i }));
    await user.click(await screen.findByRole("menuitem", { name: /renombrar/i }));

    expect(
      screen.getByRole("dialog", { name: /renombrar plantilla/i }),
    ).toBeInTheDocument();
  });

  it("hides the 'Más acciones' trigger entirely for a viewer with no permitted actions", async () => {
    const viewerTemplate: Template = {
      ...template,
      access_type: "shared",
      is_owner: false,
    };
    mockDetailResponses(viewerTemplate);
    renderDetail();

    await waitFor(() =>
      expect(screen.getByText("Contrato de Servicios")).toBeInTheDocument(),
    );

    expect(
      screen.queryByRole("button", { name: /más acciones/i }),
    ).not.toBeInTheDocument();
  });

  it("shows only the permitted 'Renombrar' item for an admin non-owner", async () => {
    const adminTemplate: Template = {
      ...template,
      access_type: "admin",
      is_owner: false,
    };
    mockDetailResponses(adminTemplate);
    const user = userEvent.setup();
    renderDetail();

    await waitFor(() =>
      expect(screen.getByText("Contrato de Servicios")).toBeInTheDocument(),
    );

    await user.click(screen.getByRole("button", { name: /más acciones/i }));

    expect(
      await screen.findByRole("menuitem", { name: /renombrar/i }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("menuitem", { name: /mover a carpeta/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("menuitem", { name: /compartir/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("menuitem", { name: /eliminar/i }),
    ).not.toBeInTheDocument();
  });
});
