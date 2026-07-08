import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import {
  VariablesTab,
  buildComputedConfig,
  buildVariableOverrides,
  initRow,
  type VariableRowState,
} from "./TemplateDetail";
import { apiClient } from "@/shared/lib/api-client";
import type { VariableMeta } from "@/features/templates/api/queries";
import type { VariableTypeOverrideInput } from "@/features/templates/api/mutations";

vi.mock("@/shared/lib/api-client", () => ({
  apiClient: {
    patch: vi.fn(),
  },
}));

const toastSuccess = vi.fn();
const toastError = vi.fn();

vi.mock("sonner", () => ({
  toast: {
    success: (...args: unknown[]) => toastSuccess(...args),
    error: (...args: unknown[]) => toastError(...args),
  },
}));

// ---------------------------------------------------------------------------
// Pure payload builder — tested in isolation, no rendering required. This is
// the part of Feature B's computed-config UI that is cheapest and most
// robust to verify directly; the rendered-component flow below additionally
// exercises the full save path end-to-end.
// ---------------------------------------------------------------------------

describe("initRow / buildComputedConfig / buildVariableOverrides (pure payload builder)", () => {
  const amountMeta: VariableMeta = { name: "amount", contexts: [], type: "decimal" };

  it("initRow seeds computed fields from an existing formula config", () => {
    const meta: VariableMeta = {
      name: "amount_with_surcharge",
      contexts: [],
      type: "decimal",
      computed: { kind: "formula", source: "amount", operator: "+", operand: 50 },
    };
    const row = initRow(meta);
    expect(row.computedEnabled).toBe(true);
    expect(row.computedKind).toBe("formula");
    expect(row.computedSource).toBe("amount");
    expect(row.computedOperator).toBe("+");
    expect(row.computedOperand).toBe("50");
  });

  it("initRow seeds computed fields from an existing function config", () => {
    const meta: VariableMeta = {
      name: "amount_in_words",
      contexts: [],
      type: "text",
      computed: { kind: "function", function: "number_to_words", source: "amount" },
    };
    const row = initRow(meta);
    expect(row.computedEnabled).toBe(true);
    expect(row.computedKind).toBe("function");
    expect(row.computedFunction).toBe("number_to_words");
    expect(row.computedSource).toBe("amount");
  });

  it("initRow leaves computed disabled for a plain variable", () => {
    expect(initRow(amountMeta).computedEnabled).toBe(false);
  });

  it("buildComputedConfig builds a formula config from row state", () => {
    const row: VariableRowState = {
      ...initRow(amountMeta),
      computedEnabled: true,
      computedKind: "formula",
      computedSource: "amount",
      computedOperator: "+",
      computedOperand: "50",
    };
    expect(buildComputedConfig(row)).toEqual({
      kind: "formula",
      source: "amount",
      operator: "+",
      operand: 50,
    });
  });

  it("buildComputedConfig defaults a non-numeric operand to 0", () => {
    const row: VariableRowState = {
      ...initRow(amountMeta),
      computedEnabled: true,
      computedKind: "formula",
      computedSource: "amount",
      computedOperator: "+",
      computedOperand: "not-a-number",
    };
    expect(buildComputedConfig(row)?.kind === "formula" && buildComputedConfig(row)).toMatchObject(
      { operand: 0 },
    );
  });

  it("buildComputedConfig returns null when computed is disabled", () => {
    expect(buildComputedConfig(initRow(amountMeta))).toBeNull();
  });

  it("buildVariableOverrides carries the computed config for a formula variable and null for a plain one", () => {
    const surchargeMeta: VariableMeta = {
      name: "amount_with_surcharge",
      contexts: [],
      type: "decimal",
    };
    const rows: Record<string, VariableRowState> = {
      amount: initRow(amountMeta),
      amount_with_surcharge: {
        ...initRow(surchargeMeta),
        computedEnabled: true,
        computedKind: "formula",
        computedSource: "amount",
        computedOperator: "+",
        computedOperand: "50",
      },
    };

    const overrides = buildVariableOverrides([amountMeta, surchargeMeta], rows);

    expect(overrides.find((o) => o.name === "amount")?.computed).toBeNull();
    expect(overrides.find((o) => o.name === "amount_with_surcharge")?.computed).toEqual({
      kind: "formula",
      source: "amount",
      operator: "+",
      operand: 50,
    });
  });

  it("never sends select options for a computed variable, even if its type field is stale as 'select'", () => {
    const meta: VariableMeta = { name: "weird", contexts: [], type: "select" };
    const row: VariableRowState = {
      ...initRow(meta),
      optionsText: "A\nB",
      computedEnabled: true,
      computedKind: "formula",
      computedSource: "amount",
      computedOperator: "+",
      computedOperand: "10",
    };
    const overrides = buildVariableOverrides([meta], { weird: row });
    expect(overrides[0].options).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// Rendered component — the full "toggle computed → pick source/operator/
// operand → save" flow, asserting the exact PATCH payload built by handleSave.
// ---------------------------------------------------------------------------

function renderTab(variablesMeta: VariableMeta[]) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <VariablesTab
        templateId="template-1"
        versionId="version-1"
        variablesMeta={variablesMeta}
        isOwner
      />
    </QueryClientProvider>,
  );
}

describe("VariablesTab — computed configuration UI", () => {
  const variablesMeta: VariableMeta[] = [
    { name: "amount", contexts: [], type: "decimal" },
    { name: "amount_with_surcharge", contexts: [], type: "decimal" },
  ];

  beforeEach(() => {
    vi.mocked(apiClient.patch).mockReset();
    toastSuccess.mockReset();
    toastError.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("builds the right computed payload (source/operator/operand) on save", async () => {
    vi.mocked(apiClient.patch).mockResolvedValue({ data: {} });
    const user = userEvent.setup();
    renderTab(variablesMeta);

    // Select the target variable in the left rail.
    await user.click(screen.getByText("amount_with_surcharge"));

    // Enable "Variable calculada".
    await user.click(screen.getByLabelText("Variable calculada"));

    // Comboboxes render in JSX order once the computed section is visible:
    // [0] Tipo de dato (now disabled), [1] Tipo de cálculo, [2] Variable de
    // origen, [3] Operador.
    const comboboxes = screen.getAllByRole("combobox");
    expect(comboboxes).toHaveLength(4);
    expect(comboboxes[0]).toBeDisabled();

    await user.click(comboboxes[2]);
    const sourceOption = await screen.findByRole("option", { name: "amount" });
    await user.click(sourceOption);

    // Operator defaults to "+" — just fill the operand.
    await user.type(screen.getByPlaceholderText("ej. 1.10"), "50");

    await user.click(screen.getByRole("button", { name: /guardar cambios/i }));

    await waitFor(() => expect(apiClient.patch).toHaveBeenCalled());
    const [url, body] = vi.mocked(apiClient.patch).mock.calls[0];
    expect(url).toBe(
      "/templates/template-1/versions/version-1/variables-meta",
    );
    const overrides = (body as { overrides: VariableTypeOverrideInput[] })
      .overrides;
    expect(
      overrides.find((o) => o.name === "amount_with_surcharge")?.computed,
    ).toEqual({
      kind: "formula",
      source: "amount",
      operator: "+",
      operand: 50,
    });
    expect(toastSuccess).toHaveBeenCalledWith("Cambios guardados");
  });

  it("only offers numeric, non-computed variables as a computed source", async () => {
    const withTextVar: VariableMeta[] = [
      { name: "amount", contexts: [], type: "decimal" },
      { name: "label", contexts: [], type: "text" },
      { name: "amount_with_surcharge", contexts: [], type: "decimal" },
    ];
    const user = userEvent.setup();
    renderTab(withTextVar);

    await user.click(screen.getByText("amount_with_surcharge"));
    await user.click(screen.getByLabelText("Variable calculada"));

    const comboboxes = screen.getAllByRole("combobox");
    await user.click(comboboxes[2]); // Variable de origen

    // "amount" (decimal) is offered; "label" (text) and the variable being
    // configured itself are not.
    expect(await screen.findByRole("option", { name: "amount" })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "label" })).not.toBeInTheDocument();
    expect(
      screen.queryByRole("option", { name: "amount_with_surcharge" }),
    ).not.toBeInTheDocument();
  });

  it("blocks saving and shows a toast when the formula operator is ÷ with operand 0", async () => {
    const user = userEvent.setup();
    renderTab(variablesMeta);

    await user.click(screen.getByText("amount_with_surcharge"));
    await user.click(screen.getByLabelText("Variable calculada"));

    const comboboxes = screen.getAllByRole("combobox");
    await user.click(comboboxes[2]); // Variable de origen
    await user.click(await screen.findByRole("option", { name: "amount" }));

    // Switch operator to ÷ and leave the operand at its default "0".
    const operatorCombobox = screen.getAllByRole("combobox")[3];
    await user.click(operatorCombobox);
    await user.click(await screen.findByRole("option", { name: "÷" }));
    await user.clear(screen.getByPlaceholderText("ej. 1.10"));
    await user.type(screen.getByPlaceholderText("ej. 1.10"), "0");

    // Inline hint is visible before even attempting to save.
    expect(
      screen.getByText(/el operando no puede ser 0 cuando el operador es ÷/i),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /guardar cambios/i }));

    expect(apiClient.patch).not.toHaveBeenCalled();
    expect(toastError).toHaveBeenCalledWith(
      'La variable calculada "amount_with_surcharge" no puede dividir por 0.',
    );
  });

  it("blocks saving and shows a toast when the formula operand is empty, even for a non-÷ operator", async () => {
    const user = userEvent.setup();
    renderTab(variablesMeta);

    await user.click(screen.getByText("amount_with_surcharge"));
    await user.click(screen.getByLabelText("Variable calculada"));

    const comboboxes = screen.getAllByRole("combobox");
    await user.click(comboboxes[2]); // Variable de origen
    await user.click(await screen.findByRole("option", { name: "amount" }));

    // Switch operator to "*" and leave the operand blank.
    const operatorCombobox = screen.getAllByRole("combobox")[3];
    await user.click(operatorCombobox);
    await user.click(await screen.findByRole("option", { name: "×" }));

    // Inline hint is visible before even attempting to save.
    expect(
      screen.getByText(/el operando debe ser un número válido/i),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /guardar cambios/i }));

    expect(apiClient.patch).not.toHaveBeenCalled();
    expect(toastError).toHaveBeenCalledWith(
      "El operando debe ser un número válido.",
    );
  });
});
