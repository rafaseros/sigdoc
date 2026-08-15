import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { VariableSourceChips } from "./VariableSourceChips";
import type { TemplateVersionFile } from "@/features/templates/api/queries";

function makeFile(
  id: string,
  label: string,
  variables: string[],
): TemplateVersionFile {
  return {
    id,
    label,
    variables,
    file_size: 1024,
    position: 0,
    created_at: "2026-01-01T00:00:00Z",
  };
}

describe("VariableSourceChips", () => {
  it("renders the 'También en:' prefix and each matching file's label chip", () => {
    render(
      <VariableSourceChips
        variableName="monto"
        files={[makeFile("f1", "Anexo A", ["monto"])]}
      />,
    );

    expect(screen.getByText("También en:")).toBeInTheDocument();
    const chip = screen.getByText("Anexo A");
    expect(chip).toBeInTheDocument();
    // The label renders inside a compact `.var-chip` badge.
    expect(chip.closest(".var-chip")).not.toBeNull();
  });

  it("renders nothing when no related file uses the variable", () => {
    const { container } = render(
      <VariableSourceChips
        variableName="fecha"
        files={[makeFile("f1", "Anexo A", ["monto"])]}
      />,
    );

    expect(container).toBeEmptyDOMElement();
    expect(screen.queryByText("También en:")).toBeNull();
  });

  it("shows every related file that uses the variable", () => {
    render(
      <VariableSourceChips
        variableName="monto"
        files={[
          makeFile("f1", "Anexo A", ["monto"]),
          makeFile("f2", "Recibo de pago", ["monto", "fecha"]),
          makeFile("f3", "Carta", ["fecha"]),
        ]}
      />,
    );

    expect(screen.getByText("Anexo A")).toBeInTheDocument();
    expect(screen.getByText("Recibo de pago")).toBeInTheDocument();
    // 'Carta' does not use 'monto' → it is never listed.
    expect(screen.queryByText("Carta")).toBeNull();
  });
});
