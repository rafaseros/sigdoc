import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { LoginPage } from "./login";
import { APP_VERSION, CHANGELOG } from "@/shared/version";

const navigateMock = vi.fn();
const loginMock = vi.fn();
const toastSuccess = vi.fn();
const toastError = vi.fn();

vi.mock("@tanstack/react-router", () => ({
  createFileRoute: () => (options: unknown) => options,
  redirect: vi.fn(),
  useNavigate: () => navigateMock,
}));

vi.mock("@/shared/lib/auth", () => ({
  useAuth: () => ({ login: (...args: unknown[]) => loginMock(...args) }),
}));

vi.mock("sonner", () => ({
  toast: {
    success: (...args: unknown[]) => toastSuccess(...args),
    error: (...args: unknown[]) => toastError(...args),
  },
}));

describe("LoginPage", () => {
  beforeEach(() => {
    navigateMock.mockReset();
    loginMock.mockReset();
    toastSuccess.mockReset();
    toastError.mockReset();
  });

  it("renders the marketing summary with the version badge", () => {
    render(<LoginPage />);

    expect(screen.getByText("Plantillas Word con variables")).toBeInTheDocument();
    expect(screen.getByText("Generación individual y masiva")).toBeInTheDocument();
    expect(
      screen.getByText("Documentos relacionados que comparten variables"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Plantillas desde un documento ejemplo"),
    ).toBeInTheDocument();
    expect(screen.getByText("Vista previa y exportación a PDF")).toBeInTheDocument();
    expect(
      screen.getByText("Datos guardados y variables calculadas"),
    ).toBeInTheDocument();

    expect(screen.getAllByText(`v${APP_VERSION}`).length).toBeGreaterThan(0);
  });

  it("submits credentials and navigates on success", async () => {
    loginMock.mockResolvedValue(undefined);
    const user = userEvent.setup();
    render(<LoginPage />);

    await user.type(
      screen.getByLabelText(/correo electrónico/i),
      "ana@empresa.com",
    );
    await user.type(screen.getByLabelText(/contraseña/i), "secreta123");
    await user.click(screen.getByRole("button", { name: /iniciar sesión/i }));

    await waitFor(() =>
      expect(loginMock).toHaveBeenCalledWith("ana@empresa.com", "secreta123"),
    );
    await waitFor(() =>
      expect(toastSuccess).toHaveBeenCalledWith("Inicio de sesión exitoso"),
    );
    expect(navigateMock).toHaveBeenCalledWith({ to: "/templates" });
  });

  it("shows an error toast when credentials are rejected", async () => {
    loginMock.mockRejectedValue(new Error("invalid"));
    const user = userEvent.setup();
    render(<LoginPage />);

    await user.type(screen.getByLabelText(/correo electrónico/i), "ana@empresa.com");
    await user.type(screen.getByLabelText(/contraseña/i), "incorrecta");
    await user.click(screen.getByRole("button", { name: /iniciar sesión/i }));

    await waitFor(() =>
      expect(toastError).toHaveBeenCalledWith("Credenciales inválidas"),
    );
    expect(navigateMock).not.toHaveBeenCalled();
  });

  it("opens the changelog dialog from the Novedades link", async () => {
    const user = userEvent.setup();
    render(<LoginPage />);

    expect(screen.queryByText(CHANGELOG[0].title)).not.toBeInTheDocument();

    await user.click(
      screen.getAllByRole("button", { name: /novedades/i })[0],
    );

    expect(await screen.findByText(CHANGELOG[0].title)).toBeInTheDocument();
    expect(screen.getByText(`v${CHANGELOG[0].version}`)).toBeInTheDocument();
  });
});
