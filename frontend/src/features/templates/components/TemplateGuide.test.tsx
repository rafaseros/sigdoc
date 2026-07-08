import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { TemplateGuideButton } from "./TemplateGuide";

describe("TemplateGuideButton — help center topics", () => {
  it("opens on 'Subir plantillas' by default", async () => {
    const user = userEvent.setup();
    render(<TemplateGuideButton />);

    await user.click(screen.getByRole("button", { name: /^guía$/i }));

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(
      screen.getByRole("tab", { name: /subir plantillas/i }),
    ).toHaveAttribute("aria-selected", "true");
    expect(screen.getByText(/variables básicas/i)).toBeInTheDocument();
  });

  it("opens directly on 'Variables calculadas' when initialTopic='computed'", async () => {
    const user = userEvent.setup();
    render(<TemplateGuideButton initialTopic="computed" />);

    await user.click(screen.getByRole("button", { name: /^guía$/i }));

    expect(
      screen.getByRole("tab", { name: /variables calculadas/i }),
    ).toHaveAttribute("aria-selected", "true");
    expect(screen.getByText(/número a literal/i)).toBeInTheDocument();
    expect(
      screen.getByText("1500.50 → UN MIL QUINIENTOS 50/100"),
    ).toBeInTheDocument();
  });

  it("opens directly on 'Generar documentos' for the compact editor variant", async () => {
    const user = userEvent.setup();
    render(<TemplateGuideButton compact initialTopic="generate" />);

    const trigger = screen.getByRole("button", { name: "Guía" });
    await user.click(trigger);

    expect(
      screen.getByRole("tab", { name: /generar documentos/i }),
    ).toHaveAttribute("aria-selected", "true");
    expect(screen.getByText(/datos guardados \(presets\)/i)).toBeInTheDocument();
  });

  it("opens directly on 'Organizar'", async () => {
    const user = userEvent.setup();
    render(<TemplateGuideButton initialTopic="organize" />);

    await user.click(screen.getByRole("button", { name: /^guía$/i }));

    expect(
      screen.getByRole("tab", { name: /organizar/i }),
    ).toHaveAttribute("aria-selected", "true");
    expect(
      screen.getByText(/las plantillas no se eliminan; quedan sin carpeta/i),
    ).toBeInTheDocument();
  });

  it("switches topics on click and can navigate away from the initial one", async () => {
    const user = userEvent.setup();
    render(<TemplateGuideButton />);

    await user.click(screen.getByRole("button", { name: /^guía$/i }));
    await user.click(screen.getByRole("tab", { name: /generar documentos/i }));

    expect(
      screen.getByRole("tab", { name: /generar documentos/i }),
    ).toHaveAttribute("aria-selected", "true");
    expect(screen.getByText(/edición en línea/i)).toBeInTheDocument();
  });

  it("resets to the initial topic every time the dialog is reopened", async () => {
    const user = userEvent.setup();
    render(<TemplateGuideButton initialTopic="upload" />);

    await user.click(screen.getByRole("button", { name: /^guía$/i }));
    await user.click(screen.getByRole("tab", { name: /organizar/i }));
    await user.click(screen.getByRole("button", { name: /close/i }));

    await user.click(screen.getByRole("button", { name: /^guía$/i }));
    expect(
      screen.getByRole("tab", { name: /subir plantillas/i }),
    ).toHaveAttribute("aria-selected", "true");
  });
});
