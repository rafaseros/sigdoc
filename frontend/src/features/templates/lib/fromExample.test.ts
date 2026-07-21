import { describe, expect, it } from "vitest";

import type { TemplateStructure } from "../api/queries";
import {
  addMapping,
  buildExistingVariableOptions,
  countEffectiveOccurrences,
  countOccurrences,
  countOccurrencesInText,
  filterVariableOptions,
  isValidVariableName,
  newVariableNames,
  normalizeSelectionText,
  parseFromExampleError,
  readParagraphSelection,
  segmentText,
  suggestVariableName,
  type VariableMapping,
} from "./fromExample";

// ---------------------------------------------------------------------------
// isValidVariableName
// ---------------------------------------------------------------------------

describe("isValidVariableName", () => {
  it.each([
    "monto",
    "nombre_cliente",
    "_interno",
    "a",
    "v2",
    "x_1_y",
  ])("accepts %s", (name) => {
    expect(isValidVariableName(name)).toBe(true);
  });

  it.each([
    "",
    "Monto",
    "1monto",
    "nombre cliente",
    "nombre-cliente",
    "señor",
    "monto!",
    " monto",
    "monto ",
    "MONTO",
  ])("rejects %j", (name) => {
    expect(isValidVariableName(name)).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// normalizeSelectionText
// ---------------------------------------------------------------------------

describe("normalizeSelectionText", () => {
  it("trims leading and trailing whitespace", () => {
    expect(normalizeSelectionText("  Juan Pérez  ")).toBe("Juan Pérez");
  });

  it("trims newlines and tabs", () => {
    expect(normalizeSelectionText("\n\tACME S.R.L.\t\n")).toBe("ACME S.R.L.");
  });

  it("preserves internal whitespace exactly", () => {
    expect(normalizeSelectionText(" a  b ")).toBe("a  b");
  });

  it("returns empty string for whitespace-only input", () => {
    expect(normalizeSelectionText("   \n\t ")).toBe("");
  });

  it("returns empty string for empty input", () => {
    expect(normalizeSelectionText("")).toBe("");
  });
});

// ---------------------------------------------------------------------------
// suggestVariableName
// ---------------------------------------------------------------------------

describe("suggestVariableName", () => {
  it("lowercases and snake_cases plain words", () => {
    expect(suggestVariableName("Juan Perez")).toBe("juan_perez");
  });

  it("strips diacritics to plain ascii", () => {
    expect(suggestVariableName("Juan Pérez Ñoño")).toBe("juan_perez_nono");
  });

  it("collapses runs of non-alphanumeric characters into one underscore", () => {
    expect(suggestVariableName("ACME  S.R.L.")).toBe("acme_s_r_l");
  });

  it("trims leading/trailing underscores produced by punctuation", () => {
    expect(suggestVariableName("¡Hola!")).toBe("hola");
  });

  it("prefixes names that would start with a digit", () => {
    expect(suggestVariableName("2024 contrato")).toBe("var_2024_contrato");
  });

  it("keeps digits and underscores in the middle", () => {
    expect(suggestVariableName("Cláusula 3b")).toBe("clausula_3b");
  });

  it("returns empty string when nothing usable remains", () => {
    expect(suggestVariableName("¡¿?!")).toBe("");
    expect(suggestVariableName("")).toBe("");
    expect(suggestVariableName("   ")).toBe("");
  });

  it("always produces a valid variable name when non-empty", () => {
    for (const raw of [
      "Juan Pérez",
      "2024",
      "  monto TOTAL  ",
      "N° de contrato",
    ]) {
      const suggested = suggestVariableName(raw);
      expect(suggested === "" || isValidVariableName(suggested)).toBe(true);
    }
  });

  it("caps very long selections to a reasonable identifier length", () => {
    const long = "palabra ".repeat(30);
    expect(suggestVariableName(long).length).toBeLessThanOrEqual(50);
    expect(isValidVariableName(suggestVariableName(long))).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// countOccurrencesInText
// ---------------------------------------------------------------------------

describe("countOccurrencesInText", () => {
  it("counts multiple non-overlapping occurrences", () => {
    expect(countOccurrencesInText("abc abc abc", "abc")).toBe(3);
  });

  it("counts non-overlapping matches only", () => {
    expect(countOccurrencesInText("aaa", "aa")).toBe(1);
  });

  it("is case-sensitive", () => {
    expect(countOccurrencesInText("Juan juan JUAN", "Juan")).toBe(1);
  });

  it("returns 0 for no match", () => {
    expect(countOccurrencesInText("hola mundo", "adios")).toBe(0);
  });

  it("returns 0 for empty needle", () => {
    expect(countOccurrencesInText("hola", "")).toBe(0);
  });
});

// ---------------------------------------------------------------------------
// countOccurrences (whole structure)
// ---------------------------------------------------------------------------

const structure: TemplateStructure = {
  headers: [
    {
      kind: "paragraph",
      level: 0,
      spans: [{ text: "ACME S.R.L. — contrato", variable: null }],
      rows: [],
    },
  ],
  body: [
    {
      kind: "heading",
      level: 1,
      spans: [{ text: "Contrato de Juan Pérez", variable: null }],
      rows: [],
    },
    {
      kind: "paragraph",
      level: 0,
      spans: [
        {
          text: "Entre ACME S.R.L. y Juan Pérez, en adelante Juan Pérez.",
          variable: null,
        },
      ],
      rows: [],
    },
    {
      kind: "list_bullet",
      level: 1,
      spans: [{ text: "Firma: Juan Pérez", variable: null }],
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
                  spans: [{ text: "Cliente: Juan Pérez", variable: null }],
                  rows: [],
                },
              ],
            },
            {
              nodes: [
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
                                { text: "Anexo de Juan Pérez", variable: null },
                              ],
                              rows: [],
                            },
                          ],
                        },
                      ],
                    },
                  ],
                },
              ],
            },
          ],
        },
      ],
    },
  ],
  footers: [
    {
      kind: "paragraph",
      level: 0,
      spans: [{ text: "Página firmada por Juan Pérez", variable: null }],
      rows: [],
    },
  ],
};

describe("countOccurrences", () => {
  it("counts across headers, body, footers and nested table cells", () => {
    // heading(1) + paragraph(2) + list(1) + cell(1) + nested-table cell(1) + footer(1)
    expect(countOccurrences(structure, "Juan Pérez")).toBe(7);
  });

  it("counts header-only text", () => {
    expect(countOccurrences(structure, "ACME S.R.L.")).toBe(2);
  });

  it("is exact and case-sensitive", () => {
    expect(countOccurrences(structure, "juan pérez")).toBe(0);
  });

  it("returns 0 for text not present", () => {
    expect(countOccurrences(structure, "inexistente")).toBe(0);
  });

  it("returns 0 for empty text", () => {
    expect(countOccurrences(structure, "")).toBe(0);
  });

  it("does not count across span boundaries", () => {
    const multiSpan: TemplateStructure = {
      headers: [],
      footers: [],
      body: [
        {
          kind: "paragraph",
          level: 0,
          spans: [
            { text: "Juan ", variable: null },
            { text: "Pérez", variable: null },
          ],
          rows: [],
        },
      ],
    };
    expect(countOccurrences(multiSpan, "Juan Pérez")).toBe(0);
    expect(countOccurrences(multiSpan, "Pérez")).toBe(1);
  });
});

// ---------------------------------------------------------------------------
// countEffectiveOccurrences
// ---------------------------------------------------------------------------

describe("countEffectiveOccurrences", () => {
  function singleParagraph(text: string): TemplateStructure {
    return {
      headers: [],
      footers: [],
      body: [
        {
          kind: "paragraph",
          level: 0,
          spans: [{ text, variable: null }],
          rows: [],
        },
      ],
    };
  }

  it("longer mapping consumes the contained shorter text — longer added first", () => {
    const doc = singleParagraph("Contrato de Juan Pérez");
    const mappings: VariableMapping[] = [
      { text: "Juan Pérez", variable: "nombre_completo" },
      { text: "Juan", variable: "nombre" },
    ];
    const counts = countEffectiveOccurrences(doc, mappings);
    expect(counts.get("Juan Pérez")).toBe(1);
    expect(counts.get("Juan")).toBe(0);
  });

  it("longer mapping consumes the contained shorter text — shorter added first", () => {
    const doc = singleParagraph("Contrato de Juan Pérez");
    const mappings: VariableMapping[] = [
      { text: "Juan", variable: "nombre" },
      { text: "Juan Pérez", variable: "nombre_completo" },
    ];
    const counts = countEffectiveOccurrences(doc, mappings);
    expect(counts.get("Juan Pérez")).toBe(1);
    expect(counts.get("Juan")).toBe(0);
  });

  it("non-overlapping mappings keep their raw counts", () => {
    const mappings: VariableMapping[] = [
      { text: "Juan Pérez", variable: "nombre" },
      { text: "ACME S.R.L.", variable: "empresa" },
    ];
    const counts = countEffectiveOccurrences(structure, mappings);
    expect(counts.get("Juan Pérez")).toBe(countOccurrences(structure, "Juan Pérez"));
    expect(counts.get("ACME S.R.L.")).toBe(
      countOccurrences(structure, "ACME S.R.L."),
    );
  });

  it("counts only the occurrence OUTSIDE the longer mapping's match", () => {
    const doc = singleParagraph("Juan Pérez saluda a Juan");
    const mappings: VariableMapping[] = [
      { text: "Juan Pérez", variable: "nombre_completo" },
      { text: "Juan", variable: "nombre" },
    ];
    const counts = countEffectiveOccurrences(doc, mappings);
    expect(counts.get("Juan Pérez")).toBe(1);
    expect(counts.get("Juan")).toBe(1);
  });

  it("simulates per blob across headers, body, footers and nested cells", () => {
    const mappings: VariableMapping[] = [
      { text: "Juan Pérez", variable: "nombre_completo" },
      { text: "Juan", variable: "nombre" },
    ];
    const counts = countEffectiveOccurrences(structure, mappings);
    // Every "Juan" in the shared fixture lives inside a "Juan Pérez"
    expect(counts.get("Juan Pérez")).toBe(7);
    expect(counts.get("Juan")).toBe(0);
  });

  it("returns zeroed entries for every mapping when nothing matches", () => {
    const counts = countEffectiveOccurrences(singleParagraph("nada"), [
      { text: "Juan", variable: "nombre" },
    ]);
    expect(counts.get("Juan")).toBe(0);
  });

  it("returns an empty map for no mappings", () => {
    expect(countEffectiveOccurrences(structure, []).size).toBe(0);
  });
});

// ---------------------------------------------------------------------------
// addMapping
// ---------------------------------------------------------------------------

describe("addMapping", () => {
  const existing: VariableMapping[] = [
    { text: "Juan Pérez", variable: "nombre_cliente" },
  ];

  it("appends a valid mapping without mutating the input", () => {
    const result = addMapping(existing, "ACME S.R.L.", "empresa");
    expect(result).toEqual({
      ok: true,
      mappings: [
        { text: "Juan Pérez", variable: "nombre_cliente" },
        { text: "ACME S.R.L.", variable: "empresa" },
      ],
    });
    expect(existing).toHaveLength(1);
  });

  it("normalizes (trims) the text before adding", () => {
    const result = addMapping([], "  ACME  ", "empresa");
    expect(result).toEqual({
      ok: true,
      mappings: [{ text: "ACME", variable: "empresa" }],
    });
  });

  it("rejects a duplicate exact text", () => {
    expect(addMapping(existing, "Juan Pérez", "otro_nombre")).toEqual({
      ok: false,
      reason: "duplicate_text",
    });
  });

  it("rejects a duplicate that only differs by surrounding whitespace", () => {
    expect(addMapping(existing, "  Juan Pérez ", "otro_nombre")).toEqual({
      ok: false,
      reason: "duplicate_text",
    });
  });

  it("allows the same variable for two different texts", () => {
    const result = addMapping(existing, "J. Pérez", "nombre_cliente");
    expect(result.ok).toBe(true);
  });

  it("rejects an invalid variable name", () => {
    expect(addMapping([], "ACME", "Empresa")).toEqual({
      ok: false,
      reason: "invalid_variable",
    });
    expect(addMapping([], "ACME", "")).toEqual({
      ok: false,
      reason: "invalid_variable",
    });
  });

  it("rejects empty or whitespace-only text", () => {
    expect(addMapping([], "   ", "empresa")).toEqual({
      ok: false,
      reason: "empty_text",
    });
    expect(addMapping([], "", "empresa")).toEqual({
      ok: false,
      reason: "empty_text",
    });
  });
});

// ---------------------------------------------------------------------------
// segmentText
// ---------------------------------------------------------------------------

describe("segmentText", () => {
  const mappings: VariableMapping[] = [
    { text: "Juan Pérez", variable: "nombre_cliente" },
    { text: "ACME", variable: "empresa" },
  ];

  it("returns a single plain segment when there are no mappings", () => {
    expect(segmentText("hola mundo", [])).toEqual([
      { text: "hola mundo", mapping: null },
    ]);
  });

  it("returns a single plain segment when nothing matches", () => {
    expect(segmentText("hola mundo", mappings)).toEqual([
      { text: "hola mundo", mapping: null },
    ]);
  });

  it("splits around a match in the middle", () => {
    expect(segmentText("Sr. Juan Pérez, presente", mappings)).toEqual([
      { text: "Sr. ", mapping: null },
      { text: "Juan Pérez", mapping: mappings[0] },
      { text: ", presente", mapping: null },
    ]);
  });

  it("handles a match at the start and end", () => {
    expect(segmentText("ACME contrata a Juan Pérez", mappings)).toEqual([
      { text: "ACME", mapping: mappings[1] },
      { text: " contrata a ", mapping: null },
      { text: "Juan Pérez", mapping: mappings[0] },
    ]);
  });

  it("marks every repeated occurrence", () => {
    expect(segmentText("ACME y ACME", mappings)).toEqual([
      { text: "ACME", mapping: mappings[1] },
      { text: " y ", mapping: null },
      { text: "ACME", mapping: mappings[1] },
    ]);
  });

  it("maps the whole text when it equals a mapping exactly", () => {
    expect(segmentText("Juan Pérez", mappings)).toEqual([
      { text: "Juan Pérez", mapping: mappings[0] },
    ]);
  });

  it("prefers the earliest match, then the longest at the same position", () => {
    const overlapping: VariableMapping[] = [
      { text: "abc", variable: "corto" },
      { text: "abcd", variable: "largo" },
    ];
    expect(segmentText("abc abcd", overlapping)).toEqual([
      { text: "abc", mapping: overlapping[0] },
      { text: " ", mapping: null },
      { text: "abcd", mapping: overlapping[1] },
    ]);
  });

  it("returns an empty array for empty text", () => {
    expect(segmentText("", mappings)).toEqual([]);
  });

  it("ignores mappings with empty text", () => {
    expect(
      segmentText("hola", [{ text: "", variable: "vacio" }]),
    ).toEqual([{ text: "hola", mapping: null }]);
  });
});

// ---------------------------------------------------------------------------
// parseFromExampleError
// ---------------------------------------------------------------------------

describe("parseFromExampleError", () => {
  const fallback = "Error al crear la plantilla";

  it("passes a plain string detail through", () => {
    expect(parseFromExampleError("Ya existe una plantilla", fallback)).toEqual({
      message: "Ya existe una plantilla",
      items: [],
    });
  });

  it("extracts message + errors[] from schema-invalid mappings", () => {
    expect(
      parseFromExampleError(
        {
          message: "Mappings inválidos",
          errors: ["mappings.0.variable: inválido"],
        },
        fallback,
      ),
    ).toEqual({
      message: "Mappings inválidos",
      items: ["mappings.0.variable: inválido"],
    });
  });

  it("extracts message + missing_texts[] when texts are not found", () => {
    expect(
      parseFromExampleError(
        {
          message: "Textos no encontrados en el documento",
          missing_texts: ["Juan Pérez", "ACME"],
        },
        fallback,
      ),
    ).toEqual({
      message: "Textos no encontrados en el documento",
      items: ["Juan Pérez", "ACME"],
    });
  });

  it("falls back for null / undefined / unknown shapes", () => {
    expect(parseFromExampleError(null, fallback)).toEqual({
      message: fallback,
      items: [],
    });
    expect(parseFromExampleError(undefined, fallback)).toEqual({
      message: fallback,
      items: [],
    });
    expect(parseFromExampleError(42, fallback)).toEqual({
      message: fallback,
      items: [],
    });
    expect(parseFromExampleError({ other: true }, fallback)).toEqual({
      message: fallback,
      items: [],
    });
  });

  it("tolerates a message-only object", () => {
    expect(parseFromExampleError({ message: "Algo salió mal" }, fallback)).toEqual(
      { message: "Algo salió mal", items: [] },
    );
  });
});

// ---------------------------------------------------------------------------
// readParagraphSelection — selection math isolated from window.getSelection.
// jsdom can build the DOM; the Selection object is faked since jsdom's
// implementation is limited.
// ---------------------------------------------------------------------------

function buildDoc(): {
  root: HTMLElement;
  p1: HTMLElement;
  p2: HTMLElement;
  outside: HTMLElement;
} {
  const root = document.createElement("div");
  root.innerHTML = [
    '<p data-selectable-paragraph="true">Entre <mark>ACME</mark> y Juan Pérez</p>',
    '<p data-selectable-paragraph="true">Segunda cláusula</p>',
  ].join("");
  const outside = document.createElement("p");
  outside.textContent = "fuera del documento";
  document.body.appendChild(root);
  document.body.appendChild(outside);
  const [p1, p2] = Array.from(
    root.querySelectorAll<HTMLElement>("[data-selectable-paragraph]"),
  );
  return { root, p1, p2, outside };
}

function fakeSelection(overrides: {
  anchorNode: Node | null;
  focusNode: Node | null;
  toString: string;
  isCollapsed?: boolean;
  rangeCount?: number;
}): Selection {
  return {
    anchorNode: overrides.anchorNode,
    focusNode: overrides.focusNode,
    isCollapsed: overrides.isCollapsed ?? false,
    rangeCount: overrides.rangeCount ?? 1,
    toString: () => overrides.toString,
    getRangeAt: () => ({
      getBoundingClientRect: () => new DOMRect(10, 20, 100, 16),
    }),
  } as unknown as Selection;
}

describe("readParagraphSelection", () => {
  it("accepts a selection fully inside one paragraph and trims the text", () => {
    const { root, p1 } = buildDoc();
    const selection = fakeSelection({
      anchorNode: p1.firstChild,
      focusNode: p1.firstChild,
      toString: "  Entre  ",
    });
    const result = readParagraphSelection(root, selection);
    expect(result).not.toBeNull();
    expect(result?.text).toBe("Entre");
  });

  it("accepts a selection crossing a highlight <mark> inside the same paragraph", () => {
    const { root, p1 } = buildDoc();
    const mark = p1.querySelector("mark")!;
    const selection = fakeSelection({
      anchorNode: p1.firstChild,
      focusNode: mark.firstChild,
      toString: "Entre ACME",
    });
    expect(readParagraphSelection(root, selection)?.text).toBe("Entre ACME");
  });

  it("rejects a null selection", () => {
    const { root } = buildDoc();
    expect(readParagraphSelection(root, null)).toBeNull();
  });

  it("rejects a collapsed selection", () => {
    const { root, p1 } = buildDoc();
    const selection = fakeSelection({
      anchorNode: p1.firstChild,
      focusNode: p1.firstChild,
      toString: "",
      isCollapsed: true,
    });
    expect(readParagraphSelection(root, selection)).toBeNull();
  });

  it("rejects a selection with no ranges", () => {
    const { root, p1 } = buildDoc();
    const selection = fakeSelection({
      anchorNode: p1.firstChild,
      focusNode: p1.firstChild,
      toString: "Entre",
      rangeCount: 0,
    });
    expect(readParagraphSelection(root, selection)).toBeNull();
  });

  it("rejects a cross-paragraph selection", () => {
    const { root, p1, p2 } = buildDoc();
    const selection = fakeSelection({
      anchorNode: p1.firstChild,
      focusNode: p2.firstChild,
      toString: "Juan Pérez Segunda",
    });
    expect(readParagraphSelection(root, selection)).toBeNull();
  });

  it("rejects a selection outside the rendered document", () => {
    const { root, outside } = buildDoc();
    const selection = fakeSelection({
      anchorNode: outside.firstChild,
      focusNode: outside.firstChild,
      toString: "fuera",
    });
    expect(readParagraphSelection(root, selection)).toBeNull();
  });

  it("rejects a paragraph that is not inside the given root", () => {
    const { p1 } = buildDoc();
    const otherRoot = document.createElement("div");
    const selection = fakeSelection({
      anchorNode: p1.firstChild,
      focusNode: p1.firstChild,
      toString: "Entre",
    });
    expect(readParagraphSelection(otherRoot, selection)).toBeNull();
  });

  it("rejects a whitespace-only selection", () => {
    const { root, p1 } = buildDoc();
    const selection = fakeSelection({
      anchorNode: p1.firstChild,
      focusNode: p1.firstChild,
      toString: "   ",
    });
    expect(readParagraphSelection(root, selection)).toBeNull();
  });

  it("returns the range's bounding rect for popover anchoring", () => {
    const { root, p1 } = buildDoc();
    const selection = fakeSelection({
      anchorNode: p1.firstChild,
      focusNode: p1.firstChild,
      toString: "Entre",
    });
    const result = readParagraphSelection(root, selection);
    expect(result?.rect).toMatchObject({ x: 10, y: 20, width: 100 });
  });
});

// ---------------------------------------------------------------------------
// buildExistingVariableOptions (attach-from-example: variable reuse)
// ---------------------------------------------------------------------------

describe("buildExistingVariableOptions", () => {
  it("annotates each union variable with its source — first related file label, else the primary document", () => {
    const options = buildExistingVariableOptions(
      ["name", "company", "monto"],
      [
        { label: "Recibo de pago", variables: ["monto"] },
        { label: "Factura", variables: ["monto", "company"] },
      ],
    );
    expect(options).toEqual([
      { name: "name", source: "Documento principal" },
      { name: "company", source: "Factura" },
      { name: "monto", source: "Recibo de pago" },
    ]);
  });

  it("marks everything as primary when the version has no related files", () => {
    const options = buildExistingVariableOptions(["name"], []);
    expect(options).toEqual([{ name: "name", source: "Documento principal" }]);
  });

  it("returns an empty list for an empty union", () => {
    expect(buildExistingVariableOptions([], [])).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// filterVariableOptions
// ---------------------------------------------------------------------------

describe("filterVariableOptions", () => {
  const options = [
    { name: "nombre_cliente", source: "Documento principal" },
    { name: "monto", source: "Documento principal" },
    { name: "monto_total", source: "Recibo" },
  ];

  it("returns every option for an empty or blank query", () => {
    expect(filterVariableOptions(options, "")).toEqual(options);
    expect(filterVariableOptions(options, "   ")).toEqual(options);
  });

  it("filters by case-insensitive name containment", () => {
    expect(filterVariableOptions(options, "MONTO")).toEqual([
      { name: "monto", source: "Documento principal" },
      { name: "monto_total", source: "Recibo" },
    ]);
    expect(filterVariableOptions(options, "cliente")).toEqual([
      { name: "nombre_cliente", source: "Documento principal" },
    ]);
  });

  it("returns an empty list when nothing matches", () => {
    expect(filterVariableOptions(options, "zzz")).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// newVariableNames (existente vs. nueva classification)
// ---------------------------------------------------------------------------

describe("newVariableNames", () => {
  const existing = ["name", "monto"];

  it("returns the distinct mapping variables not present in the template", () => {
    const mappings: VariableMapping[] = [
      { text: "JUAN", variable: "name" },
      { text: "15/03/2026", variable: "fecha" },
      { text: "100", variable: "monto" },
      { text: "quince de marzo", variable: "fecha" },
    ];
    expect(newVariableNames(mappings, existing)).toEqual(["fecha"]);
  });

  it("returns an empty list when every mapping reuses an existing variable", () => {
    const mappings: VariableMapping[] = [
      { text: "JUAN", variable: "name" },
      { text: "100", variable: "monto" },
    ];
    expect(newVariableNames(mappings, existing)).toEqual([]);
  });

  it("keeps first-appearance order for multiple new variables", () => {
    const mappings: VariableMapping[] = [
      { text: "b", variable: "beta" },
      { text: "a", variable: "alfa" },
      { text: "b2", variable: "beta" },
    ];
    expect(newVariableNames(mappings, [])).toEqual(["beta", "alfa"]);
  });
});
