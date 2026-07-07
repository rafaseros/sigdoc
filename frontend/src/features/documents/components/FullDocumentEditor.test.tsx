import { describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { FullDocumentEditor } from "./FullDocumentEditor";
import type {
  TemplateStructure,
  VariableMeta,
} from "@/features/templates/api/queries";

// ---------------------------------------------------------------------------
// Fixture — a body paragraph with a text variable appearing TWICE, a
// heading, a bullet list item with an integer variable, and a table with a
// select variable in a cell.
// ---------------------------------------------------------------------------

const structure: TemplateStructure = {
  headers: [],
  footers: [],
  body: [
    {
      kind: "heading",
      level: 1,
      spans: [{ text: "Contract summary", variable: null }],
      rows: [],
    },
    {
      kind: "paragraph",
      level: 0,
      spans: [
        { text: "Hello ", variable: null },
        { text: "{{ company_name }}", variable: "company_name" },
        { text: ", welcome back. Again, ", variable: null },
        { text: "{{ company_name }}", variable: "company_name" },
        { text: " thanks you.", variable: null },
      ],
      rows: [],
    },
    {
      kind: "list_bullet",
      level: 1,
      spans: [
        { text: "Units ordered: ", variable: null },
        { text: "{{ item_count }}", variable: "item_count" },
      ],
      rows: [],
    },
    {
      kind: "table",
      level: 0,
      spans: [],
      rows: [
        {
          cells: [
            {
              nodes: [
                {
                  kind: "paragraph",
                  level: 0,
                  spans: [
                    { text: "Status: ", variable: null },
                    { text: "{{ status }}", variable: "status" },
                  ],
                  rows: [],
                },
              ],
            },
          ],
        },
      ],
    },
    // Trailing paragraph with its own variable, positioned after "status" —
    // used to verify forward-only advance past an already-filled instance
    // (see test 12).
    {
      kind: "paragraph",
      level: 0,
      spans: [
        { text: "Notes: ", variable: null },
        { text: "{{ notes }}", variable: "notes" },
      ],
      rows: [],
    },
  ],
};

const variablesMeta: VariableMeta[] = [
  {
    name: "company_name",
    contexts: [],
    type: "text",
    help_text: "Enter the legal company name",
  },
  { name: "item_count", contexts: [], type: "integer" },
  {
    name: "status",
    contexts: [],
    type: "select",
    options: ["Open", "Closed"],
  },
  { name: "notes", contexts: [], type: "text" },
];

function renderEditor() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <FullDocumentEditor
        templateVersionId="version-1"
        templateName="Test Template"
        variablesMeta={variablesMeta}
        structure={structure}
      />
    </QueryClientProvider>,
  );
}

describe("FullDocumentEditor — inline pill editing", () => {
  it("1. swaps a pill for an inline input on click, with no dialog/popup role, and focuses the input", async () => {
    const user = userEvent.setup();
    renderEditor();

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

    const pills = screen.getAllByText("{{ company_name }}");
    await user.click(pills[0]);

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    const input = screen.getByRole("textbox");
    expect(input).toHaveFocus();
  });

  it("2. typing + Enter commits: input disappears, filled pill shows the value, both occurrences sync (name-keyed)", async () => {
    const user = userEvent.setup();
    renderEditor();

    const pills = screen.getAllByText("{{ company_name }}");
    await user.click(pills[0]);
    const input = screen.getByRole("textbox");
    await user.type(input, "Acme Corp");
    await user.keyboard("{Enter}");

    expect(input).not.toBeInTheDocument();
    const filled = screen.getAllByText("Acme Corp");
    expect(filled).toHaveLength(2);
  });

  it("3. Escape reverts to the previous committed value", async () => {
    const user = userEvent.setup();
    renderEditor();

    const pills = screen.getAllByText("{{ company_name }}");
    await user.click(pills[0]);
    const input = screen.getByRole("textbox");
    await user.type(input, "Wrong Value");
    await user.keyboard("{Escape}");

    expect(screen.queryAllByRole("textbox")).toHaveLength(0);
    expect(screen.queryByText("Wrong Value")).not.toBeInTheDocument();
    expect(screen.getAllByText("{{ company_name }}")).toHaveLength(2);
  });

  it("4. blur commits without advancing", async () => {
    const user = userEvent.setup();
    renderEditor();

    const pills = screen.getAllByText("{{ company_name }}");
    await user.click(pills[0]);
    const input = screen.getByRole("textbox");
    await user.type(input, "Beta LLC");
    fireEvent.blur(input);

    expect(screen.getAllByText("Beta LLC")).toHaveLength(2);
    expect(screen.queryAllByRole("textbox")).toHaveLength(0);
    expect(screen.queryAllByRole("combobox")).toHaveLength(0);
  });

  it("5. integer variable renders inputMode=numeric", async () => {
    const user = userEvent.setup();
    renderEditor();

    const pill = screen.getByText("{{ item_count }}");
    await user.click(pill);
    const input = screen.getByRole("textbox");
    expect(input).toHaveAttribute("inputmode", "numeric");
  });

  it("6. select variable renders a combobox; selecting an option commits it", async () => {
    const user = userEvent.setup();
    renderEditor();

    const pill = screen.getByText("{{ status }}");
    await user.click(pill);

    const combobox = screen.getByRole("combobox");
    expect(combobox).toBeInTheDocument();

    await user.click(combobox);
    const option = await screen.findByRole("option", { name: "Open" });
    await user.click(option);

    expect(screen.getByText("Open")).toBeInTheDocument();
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
  });

  it("7. help_text appears as the input placeholder", async () => {
    const user = userEvent.setup();
    renderEditor();

    const pills = screen.getAllByText("{{ company_name }}");
    await user.click(pills[0]);
    const input = screen.getByRole("textbox");
    expect(input).toHaveAttribute(
      "placeholder",
      "Enter the legal company name",
    );
  });

  it("8. Enter during IME composition does not commit", async () => {
    const user = userEvent.setup();
    renderEditor();

    const pills = screen.getAllByText("{{ company_name }}");
    await user.click(pills[0]);
    const input = screen.getByRole("textbox");
    await user.type(input, "Partial");
    fireEvent.keyDown(input, { key: "Enter", isComposing: true });

    // Still editing — the composing Enter must not have committed.
    expect(screen.getByRole("textbox")).toBe(input);
    expect(screen.queryByText("Partial")).not.toBeInTheDocument();
  });

  it("9. Enter on a filled commit auto-advances to the next empty variable instance", async () => {
    const user = userEvent.setup();
    renderEditor();

    const pills = screen.getAllByText("{{ company_name }}");
    await user.click(pills[0]);
    const input = screen.getByRole("textbox");
    await user.type(input, "Acme Corp");
    await user.keyboard("{Enter}");

    // Next empty instance in document order is the integer field.
    const nextInput = screen.getByRole("textbox");
    expect(nextInput).toHaveFocus();
    expect(nextInput).toHaveAttribute("inputmode", "numeric");
  });

  it("10. re-entering edit mode resets the blur-suppression guard so a later blur commits (suppressBlurRef regression)", async () => {
    const user = userEvent.setup();
    renderEditor();

    const pills = screen.getAllByText("{{ company_name }}");
    await user.click(pills[0]);
    let input = screen.getByRole("textbox");
    await user.type(input, "Acme Corp");
    await user.keyboard("{Enter}");

    // Click the SAME pill occurrence again — it now shows the committed value.
    const filledPill = screen.getAllByText("Acme Corp")[0];
    await user.click(filledPill);
    input = screen.getByRole("textbox");
    await user.clear(input);
    await user.type(input, "Zenith Inc");
    fireEvent.blur(input);

    // If the suppressBlurRef reset on re-entering edit mode is removed, a
    // stale `true` left over from the Enter-commit above silently swallows
    // this genuine blur and "Zenith Inc" never commits.
    expect(screen.getAllByText("Zenith Inc")).toHaveLength(2);
    expect(screen.queryAllByRole("textbox")).toHaveLength(0);
  });

  it("11. clicking away from a select pill without opening it reverts to the pill (no stuck editing state)", async () => {
    const user = userEvent.setup();
    renderEditor();

    const pill = screen.getByText("{{ status }}");
    await user.click(pill);

    const combobox = screen.getByRole("combobox");
    expect(combobox).toBeInTheDocument();

    // Blur the trigger without ever opening the dropdown or picking a value.
    fireEvent.blur(combobox);

    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
    expect(screen.getByText("{{ status }}")).toBeInTheDocument();
  });

  it("12. commits an earlier empty variable and advances forward past an already-filled later one to the next empty instance in document order", async () => {
    const user = userEvent.setup();
    renderEditor();

    // Pre-fill the LATER "status" variable so it's already complete.
    const statusPill = screen.getByText("{{ status }}");
    await user.click(statusPill);
    const combobox = screen.getByRole("combobox");
    await user.click(combobox);
    const option = await screen.findByRole("option", { name: "Open" });
    await user.click(option);
    expect(screen.getByText("Open")).toBeInTheDocument();

    // Commit the EARLIER, still-empty "item_count" variable.
    const itemCountPill = screen.getByText("{{ item_count }}");
    await user.click(itemCountPill);
    const input = screen.getByRole("textbox");
    await user.type(input, "42");
    await user.keyboard("{Enter}");

    // Must advance FORWARD to the next empty instance after item_count in
    // document order — "notes" — not backward to company_name, and not
    // onto "status", which is already filled.
    const nextInput = screen.getByRole("textbox");
    expect(nextInput).toHaveFocus();
    expect(nextInput).toHaveAttribute("placeholder", "notes");
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
    expect(screen.getAllByText("{{ company_name }}")).toHaveLength(2);
  });
});
