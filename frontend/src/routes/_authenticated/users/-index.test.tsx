import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import { UsersPage } from "./index";

// Mutable role stub so each test can pick the acting user's role.
let mockRole: string | null = "admin";

vi.mock("@tanstack/react-router", () => ({
  createFileRoute: () => (options: unknown) => options,
}));

vi.mock("@/shared/lib/auth", () => ({
  useAuth: () => ({ user: mockRole ? { role: mockRole } : null }),
}));

// The admin-only content mounts real feature components/queries; stub the
// whole feature module so the guard test stays focused on the role gate.
type UsersListData = {
  items: unknown[];
  total: number;
  page: number;
  size: number;
};

const useUsersMock = vi.fn<() => { data: UsersListData | undefined }>(() => ({
  data: undefined,
}));

vi.mock("@/features/users", () => ({
  useUsers: () => useUsersMock(),
  UserList: () => <div data-testid="user-list" />,
  CreateUserDialog: () => <div data-testid="create-user-dialog" />,
}));

describe("UsersPage — admin guard", () => {
  beforeEach(() => {
    useUsersMock.mockClear();
    useUsersMock.mockReturnValue({ data: undefined });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    mockRole = "admin";
  });

  it("renders the restricted state and skips the users query for a non-admin", () => {
    mockRole = "document_generator";
    render(<UsersPage />);

    expect(screen.getByText("Acceso restringido")).toBeInTheDocument();
    expect(
      screen.getByText("Solo los administradores pueden gestionar usuarios."),
    ).toBeInTheDocument();
    // The admin-only content (and its query) must never mount.
    expect(screen.queryByTestId("user-list")).not.toBeInTheDocument();
    expect(useUsersMock).not.toHaveBeenCalled();
  });

  it("renders the restricted state when there is no authenticated user", () => {
    mockRole = null;
    render(<UsersPage />);

    expect(screen.getByText("Acceso restringido")).toBeInTheDocument();
    expect(useUsersMock).not.toHaveBeenCalled();
  });

  it("renders the users management shell for an admin", () => {
    mockRole = "admin";
    useUsersMock.mockReturnValue({
      data: { items: [], total: 0, page: 1, size: 100 },
    });
    render(<UsersPage />);

    expect(screen.queryByText("Acceso restringido")).not.toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Usuarios" }),
    ).toBeInTheDocument();
    expect(screen.getByTestId("user-list")).toBeInTheDocument();
    expect(useUsersMock).toHaveBeenCalled();
  });
});
