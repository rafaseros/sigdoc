import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { RelatedFileVariables } from "./RelatedFileVariables";
import type {
  TemplateVersionFile,
  VariableMeta,
} from "@/features/templates/api/queries";

function makeFile(variables: string[]): TemplateVersionFile {
  return {
    id: "file-1",
    label: "Anexo A",
    variables,
    file_size: 2048,
    position: 0,
    created_at: "2026-01-01T00:00:00Z",
  };
}

// The version's variables_meta union: `monto` is a plain variable and
// `monto_total` is computed (server-owned, auto-calculated).
const variablesMeta: VariableMeta[] = [
  { name: "monto", contexts: [], type: "decimal" },
  {
    name: "monto_total",
    contexts: [],
    type: "decimal",
    computed: { kind: "formula", source: "monto", operator: "*", operand: 1.13 },
  },
];

describe("RelatedFileVariables", () => {
  it("renders each of the file's variable names when expanded", async () => {
    const user = userEvent.setup();
    render(
      <RelatedFileVariables
        file={makeFile(["monto", "monto_total"])}
        variablesMeta={variablesMeta}
      />,
    );

    const toggle = screen.getByRole("button", { name: /ver variables/i });
    expect(toggle).toHaveAttribute("aria-expanded", "false");

    await user.click(toggle);

    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("monto")).toBeInTheDocument();
    expect(screen.getByText("monto_total")).toBeInTheDocument();
  });

  it("styles a computed variable distinctly and marks it as automatic", async () => {
    const user = userEvent.setup();
    render(
      <RelatedFileVariables
        file={makeFile(["monto", "monto_total"])}
        variablesMeta={variablesMeta}
      />,
    );

    await user.click(screen.getByRole("button", { name: /ver variables/i }));

    // Plain variable → muted chip, no computed styling, no auto marker.
    const plainChip = screen.getByText("monto").closest("span.var-chip");
    expect(plainChip).toHaveClass("var-chip-muted");
    expect(plainChip).not.toHaveClass("var-chip-computed");
    expect(plainChip).not.toHaveTextContent(/auto/i);

    // Computed variable → computed chip + visible "auto" marker.
    const computedChip = screen
      .getByText("monto_total")
      .closest("span.var-chip");
    expect(computedChip).toHaveClass("var-chip-computed");
    expect(computedChip).not.toHaveClass("var-chip-muted");
    expect(computedChip).toHaveTextContent(/auto/i);
  });

  it("shows a 'Sin variables' line and no toggle when the file has no variables", () => {
    render(
      <RelatedFileVariables file={makeFile([])} variablesMeta={variablesMeta} />,
    );

    expect(screen.getByText(/sin variables/i)).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /ver variables/i }),
    ).not.toBeInTheDocument();
  });
});
