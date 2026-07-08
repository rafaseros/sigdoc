import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
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

function mockDetailResponses() {
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
    return { data: template };
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
