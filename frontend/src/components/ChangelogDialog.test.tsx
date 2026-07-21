import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import { ChangelogDialog } from "./ChangelogDialog";
import { CHANGELOG } from "@/shared/version";

describe("ChangelogDialog", () => {
  it("renders a section per version with badge, title and items", () => {
    render(<ChangelogDialog open onOpenChange={vi.fn()} />);

    for (const entry of CHANGELOG) {
      expect(screen.getByText(`v${entry.version}`)).toBeInTheDocument();
      expect(screen.getByText(entry.title)).toBeInTheDocument();
      for (const item of entry.items) {
        expect(screen.getByText(item)).toBeInTheDocument();
      }
    }
  });

  it("marks only the newest version as current and keeps it first", () => {
    render(<ChangelogDialog open onOpenChange={vi.fn()} />);

    expect(screen.getAllByText("Actual")).toHaveLength(1);

    const text = document.body.textContent ?? "";
    const newest = text.indexOf(`v${CHANGELOG[0].version}`);
    const oldest = text.indexOf(`v${CHANGELOG[CHANGELOG.length - 1].version}`);
    expect(newest).toBeGreaterThanOrEqual(0);
    expect(newest).toBeLessThan(oldest);
  });

  it("renders nothing while closed", () => {
    render(<ChangelogDialog open={false} onOpenChange={vi.fn()} />);

    expect(screen.queryByText("Novedades")).not.toBeInTheDocument();
    expect(screen.queryByText(`v${CHANGELOG[0].version}`)).not.toBeInTheDocument();
  });
});
