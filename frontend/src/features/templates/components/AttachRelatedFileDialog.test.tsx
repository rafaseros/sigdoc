import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { AttachRelatedFileDialog } from "./AttachRelatedFileDialog";
import { apiClient } from "@/shared/lib/api-client";

vi.mock("@/shared/lib/api-client", () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
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
}));

const DOCX_MIME =
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document";

function makeDocxFile(name = "recibo.docx"): File {
  return new File(["docx-bytes"], name, { type: DOCX_MIME });
}

function renderDialog(onOpenChange = vi.fn()) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  const utils = render(
    <QueryClientProvider client={queryClient}>
      <AttachRelatedFileDialog
        templateId="template-1"
        versionId="version-1"
        open
        onOpenChange={onOpenChange}
      />
    </QueryClientProvider>,
  );
  return { ...utils, onOpenChange };
}

/** Drop a file through the dropzone's hidden input. */
async function uploadFile(user: ReturnType<typeof userEvent.setup>) {
  const input = document.querySelector<HTMLInputElement>('input[type="file"]');
  expect(input).not.toBeNull();
  await user.upload(input!, makeDocxFile());
}

beforeEach(() => {
  vi.mocked(apiClient.post).mockReset();
  toastSuccessMock.mockReset();
  toastErrorMock.mockReset();
  navigateMock.mockReset();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("AttachRelatedFileDialog — label validation", () => {
  it("keeps the submit button disabled until both a file and a label are provided", async () => {
    const user = userEvent.setup();
    renderDialog();

    const submit = screen.getByRole("button", { name: /agregar documento/i });
    expect(submit).toBeDisabled();

    // Label alone is not enough.
    await user.type(screen.getByLabelText(/etiqueta/i), "Recibo de pago");
    expect(submit).toBeDisabled();

    // File + label enables it.
    await uploadFile(user);
    expect(submit).toBeEnabled();
  });

  it("blocks submission and shows an inline hint when the label exceeds 120 characters", async () => {
    const user = userEvent.setup();
    renderDialog();

    await uploadFile(user);
    const longLabel = "x".repeat(121);
    const labelInput = screen.getByLabelText(/etiqueta/i);
    await user.click(labelInput);
    await user.paste(longLabel);

    expect(
      screen.getByText(/no puede superar los 120 caracteres/i),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /agregar documento/i }),
    ).toBeDisabled();
  });
});

describe("AttachRelatedFileDialog — create from example", () => {
  it("offers a secondary action that closes the dialog and navigates to the attach-example flow", async () => {
    const user = userEvent.setup();
    const { onOpenChange } = renderDialog();

    await user.click(
      screen.getByRole("button", { name: /crear desde documento ejemplo/i }),
    );

    expect(onOpenChange).toHaveBeenCalledWith(false);
    expect(navigateMock).toHaveBeenCalledWith({
      to: "/templates/$templateId/attach-example",
      params: { templateId: "template-1" },
    });
  });

  it("hides the secondary action once a file was chosen for the plain upload", async () => {
    const user = userEvent.setup();
    renderDialog();

    await uploadFile(user);

    expect(
      screen.queryByRole("button", { name: /crear desde documento ejemplo/i }),
    ).not.toBeInTheDocument();
  });
});

describe("AttachRelatedFileDialog — submission", () => {
  it("posts a FormData with file + label to the version files endpoint and closes on success", async () => {
    vi.mocked(apiClient.post).mockResolvedValue({
      data: {
        id: "file-1",
        label: "Recibo de pago",
        variables: ["monto"],
        file_size: 2048,
        position: 0,
        created_at: "2026-01-01T00:00:00Z",
      },
    });
    const user = userEvent.setup();
    const { onOpenChange } = renderDialog();

    await uploadFile(user);
    await user.type(screen.getByLabelText(/etiqueta/i), "Recibo de pago");
    await user.click(screen.getByRole("button", { name: /agregar documento/i }));

    await waitFor(() => expect(apiClient.post).toHaveBeenCalledTimes(1));
    const [url, body] = vi.mocked(apiClient.post).mock.calls[0];
    expect(url).toBe("/templates/template-1/versions/version-1/files");
    expect(body).toBeInstanceOf(FormData);
    const formData = body as FormData;
    expect(formData.get("label")).toBe("Recibo de pago");
    expect((formData.get("file") as File).name).toBe("recibo.docx");

    expect(toastSuccessMock).toHaveBeenCalledWith(
      "Documento relacionado agregado",
    );
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("renders a 409 duplicate-label detail inline and keeps the dialog open", async () => {
    vi.mocked(apiClient.post).mockRejectedValue({
      response: {
        status: 409,
        data: {
          detail: "Ya existe un documento relacionado con esa etiqueta.",
        },
      },
    });
    const user = userEvent.setup();
    const { onOpenChange } = renderDialog();

    await uploadFile(user);
    await user.type(screen.getByLabelText(/etiqueta/i), "Recibo de pago");
    await user.click(screen.getByRole("button", { name: /agregar documento/i }));

    expect(
      await screen.findByText(
        "Ya existe un documento relacionado con esa etiqueta.",
      ),
    ).toBeInTheDocument();
    expect(onOpenChange).not.toHaveBeenCalledWith(false);
    expect(toastSuccessMock).not.toHaveBeenCalled();
  });

  it("renders a 422 message plus its validation issues inline", async () => {
    vi.mocked(apiClient.post).mockRejectedValue({
      response: {
        status: 422,
        data: {
          message: "La plantilla contiene errores de validación.",
          validation: {
            errors: [
              {
                type: "unclosed_tag",
                message: "Marcador sin cerrar: {{ monto",
                variable: "monto",
                fixable: true,
                suggestion: null,
              },
            ],
          },
        },
      },
    });
    const user = userEvent.setup();
    renderDialog();

    await uploadFile(user);
    await user.type(screen.getByLabelText(/etiqueta/i), "Recibo de pago");
    await user.click(screen.getByRole("button", { name: /agregar documento/i }));

    expect(
      await screen.findByText("La plantilla contiene errores de validación."),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Marcador sin cerrar: {{ monto"),
    ).toBeInTheDocument();
  });
});
