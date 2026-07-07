import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { FullDocumentEditor } from "./FullDocumentEditor";
import { apiClient } from "@/shared/lib/api-client";
import type {
  TemplateStructure,
  VariableMeta,
} from "@/features/templates/api/queries";

// The "Vista previa" flow (Feature C) hits POST /documents/preview via the
// shared apiClient — mock it at the module boundary so no live request is
// ever attempted. Tests that exercise that flow configure the resolved
// value explicitly; other tests never touch this mock.
vi.mock("@/shared/lib/api-client", () => ({
  apiClient: {
    post: vi.fn(),
    get: vi.fn(),
  },
}));

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

/** A promise plus its own resolve/reject, for tests that need to control
 * exactly when a mocked request settles (e.g. simulating an in-flight
 * request that outlives a dialog close). */
function createDeferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

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
    // 2 document pill occurrences + 1 live echo in the variables review panel.
    const filled = screen.getAllByText("Acme Corp");
    expect(filled).toHaveLength(3);
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

    // 2 document pill occurrences + 1 live echo in the variables review panel.
    expect(screen.getAllByText("Beta LLC")).toHaveLength(3);
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

    // 1 document pill occurrence + 1 live echo in the variables review panel.
    expect(screen.getAllByText("Open")).toHaveLength(2);
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
    // 2 document pill occurrences + 1 live echo in the variables review panel.
    expect(screen.getAllByText("Zenith Inc")).toHaveLength(3);
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
    // 1 document pill occurrence + 1 live echo in the variables review panel.
    expect(screen.getAllByText("Open")).toHaveLength(2);

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

  it("18. clicking a different variable's panel row while one is being edited blur-commits the current draft and opens the newly-clicked variable (fragile interaction regression)", async () => {
    const user = userEvent.setup();
    renderEditor();

    // Start editing "company_name" via its document pill, but never commit
    // it explicitly (no Enter, no manual blur).
    const pills = screen.getAllByText("{{ company_name }}");
    await user.click(pills[0]);
    const input = screen.getByRole("textbox");
    await user.type(input, "Acme Corp");

    // Click a DIFFERENT variable's row in the side panel. A real click moves
    // focus away from the still-open input first, which must blur-commit it
    // exactly like test 4, before opening the newly-clicked variable.
    await user.click(screen.getByText("item count"));

    // "Acme Corp" committed for company_name (2 document pills + 1 panel
    // echo) ...
    expect(screen.getAllByText("Acme Corp")).toHaveLength(3);
    // ... and "item_count"'s inline input is now open and focused.
    const nextInput = screen.getByRole("textbox");
    expect(nextInput).toHaveAttribute("inputmode", "numeric");
    expect(nextInput).toHaveFocus();
  });
});

describe("FullDocumentEditor — variables panel, sticky action bar, preview dialog", () => {
  const createObjectURLMock = vi.fn(() => "blob:mock-url");
  const revokeObjectURLMock = vi.fn();

  beforeEach(() => {
    vi.mocked(apiClient.post).mockReset();
    vi.mocked(apiClient.post).mockResolvedValue({
      data: new Blob(["pdf-bytes"], { type: "application/pdf" }),
    });
    createObjectURLMock.mockClear();
    revokeObjectURLMock.mockClear();
    URL.createObjectURL = createObjectURLMock as unknown as typeof URL.createObjectURL;
    URL.revokeObjectURL = revokeObjectURLMock;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("13. the panel lists every distinct variable, shows a Pendiente badge for unfilled ones, and updates live after a commit", async () => {
    const user = userEvent.setup();
    renderEditor();

    // 4 distinct variables in the fixture, none filled yet.
    expect(screen.getAllByText("Pendiente")).toHaveLength(4);
    expect(screen.getByText("company name")).toBeInTheDocument();
    expect(screen.getByText("item count")).toBeInTheDocument();
    expect(screen.getByText("status")).toBeInTheDocument();
    expect(screen.getByText("notes")).toBeInTheDocument();

    // Commit "company_name" via the inline editor (document, not panel).
    const pills = screen.getAllByText("{{ company_name }}");
    await user.click(pills[0]);
    const input = screen.getByRole("textbox");
    await user.type(input, "Acme Corp");
    await user.keyboard("{Enter}");

    // One fewer Pendiente badge; the panel row now shows the value (the
    // two document pills plus the panel row all read "Acme Corp").
    expect(screen.getAllByText("Pendiente")).toHaveLength(3);
    expect(screen.getAllByText("Acme Corp")).toHaveLength(3);
  });

  it("14. clicking an unfilled panel row opens that variable's inline input on its first instance", async () => {
    const user = userEvent.setup();
    renderEditor();

    await user.click(screen.getByText("item count"));

    const input = screen.getByRole("textbox");
    expect(input).toHaveFocus();
    expect(input).toHaveAttribute("inputmode", "numeric");
  });

  it("15. the sticky bottom bar renders progress and both action buttons; Generar documento stays disabled until every variable is filled", () => {
    renderEditor();

    expect(
      screen.getByRole("button", { name: /vista previa/i }),
    ).toBeEnabled();

    const generateButton = screen.getByRole("button", {
      name: /generar documento/i,
    });
    expect(generateButton).toBeDisabled();

    // Top progress card + sticky bar both render a progress indicator.
    expect(screen.getAllByRole("progressbar").length).toBeGreaterThan(0);
  });

  it("16. Vista previa triggers the preview request with the current partial values and opens the dialog", async () => {
    const user = userEvent.setup();
    renderEditor();

    // Fill only "company_name" — the rest stays empty. Preview must accept
    // partial values. Auto-advance opens the next (empty) field; back out of
    // it with Escape so it stays untouched instead of blur-committing "".
    const pills = screen.getAllByText("{{ company_name }}");
    await user.click(pills[0]);
    await user.type(screen.getByRole("textbox"), "Acme Corp");
    await user.keyboard("{Enter}");
    await user.keyboard("{Escape}");

    await user.click(screen.getByRole("button", { name: /vista previa/i }));

    expect(apiClient.post).toHaveBeenCalledWith(
      "/documents/preview",
      {
        template_version_id: "version-1",
        variables: { company_name: "Acme Corp" },
      },
      { responseType: "blob" },
    );

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    await waitFor(() =>
      expect(
        screen.getByTitle("Vista previa del documento"),
      ).toHaveAttribute("src", "blob:mock-url"),
    );
  });

  it("17. closing the preview dialog revokes the blob URL", async () => {
    const user = userEvent.setup();
    renderEditor();

    await user.click(screen.getByRole("button", { name: /vista previa/i }));
    await waitFor(() =>
      expect(
        screen.getByTitle("Vista previa del documento"),
      ).toHaveAttribute("src", "blob:mock-url"),
    );

    await user.click(screen.getByRole("button", { name: /close/i }));

    expect(revokeObjectURLMock).toHaveBeenCalledWith("blob:mock-url");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("19. closing the dialog before a preview resolves, then reopening while a second request is pending, never flashes the stale PDF (stale-preview regression)", async () => {
    const user = userEvent.setup();

    // Distinct object URLs per request so we can tell which one ends up
    // revoked vs. rendered.
    let urlSeq = 0;
    URL.createObjectURL = vi.fn(
      () => `blob:mock-url-${++urlSeq}`,
    ) as unknown as typeof URL.createObjectURL;

    // Two controlled requests — resolved explicitly, in order, by this test.
    const deferreds = [
      createDeferred<{ data: Blob }>(),
      createDeferred<{ data: Blob }>(),
    ];
    let callIndex = 0;
    vi.mocked(apiClient.post).mockImplementation(() => {
      const current = deferreds[callIndex];
      callIndex += 1;
      return current.promise;
    });

    renderEditor();

    // First preview request — dialog opens, request is still in flight.
    await user.click(screen.getByRole("button", { name: /vista previa/i }));
    const firstDialog = screen.getByRole("dialog");
    expect(
      within(firstDialog).getByText("Generando vista previa…"),
    ).toBeInTheDocument();

    // Close BEFORE the first request resolves.
    await user.click(screen.getByRole("button", { name: /close/i }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

    // Now let the first (stale, superseded-by-close) request resolve.
    deferreds[0].resolve({
      data: new Blob(["pdf-bytes-1"], { type: "application/pdf" }),
    });
    await waitFor(() =>
      expect(revokeObjectURLMock).toHaveBeenCalledWith("blob:mock-url-1"),
    );
    // It must never have been rendered.
    expect(
      screen.queryByTitle("Vista previa del documento"),
    ).not.toBeInTheDocument();

    // Reopen — this starts a second request that is still pending.
    await user.click(screen.getByRole("button", { name: /vista previa/i }));
    const reopenedDialog = screen.getByRole("dialog");
    expect(
      within(reopenedDialog).getByText("Generando vista previa…"),
    ).toBeInTheDocument();
    expect(
      screen.queryByTitle("Vista previa del documento"),
    ).not.toBeInTheDocument();

    // Resolving the second (current) request now renders its PDF.
    deferreds[1].resolve({
      data: new Blob(["pdf-bytes-2"], { type: "application/pdf" }),
    });
    await waitFor(() =>
      expect(
        screen.getByTitle("Vista previa del documento"),
      ).toHaveAttribute("src", "blob:mock-url-2"),
    );
  });
});
