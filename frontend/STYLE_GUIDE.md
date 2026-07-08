# SigDoc Frontend Style Guide

This is a **practical recipe book**, not theory. It distills the design system
actually shipped in `frontend/src/` — grounded in, in priority order:

1. `design/design_handoff_sigdoc/` — the original hifi mockups (`README.md`,
   `assets/colors_and_type.css`, `src/primitives.jsx`), with `src/screens-user-modals.jsx`
   / `src/screens-admin.jsx` as the **user-declared canonical reference**.
2. `frontend/src/index.css` — the 127 CSS custom properties actually shipped
   to production.
3. The **users feature** (`frontend/src/features/users/components/`) as the
   living, shipped reference implementation. When in doubt, copy its exact
   class strings — don't invent a near-miss.

UI copy is Spanish (neutral register, sentence case) — see [Copy register](#copy-register-spanish).
Everything else in this document (identifiers, comments) is English.

---

## 1. Color tokens — semantics and when to use each

All colors are CSS custom properties defined in `frontend/src/index.css`
(shadcn tokens + SigDoc semantic shorthands). **Never hardcode a color that
already has a token** — the two exceptions are the raw hex values baked into
gradients/rings below (`#004ac6`, `#2563eb`, etc.), which are used verbatim
throughout the codebase for the brand gradient because Tailwind's
`bg-gradient-to-br from-[...] to-[...]` doesn't resolve CSS vars inside
`from-`/`to-` reliably in every build — this is an accepted, intentional
exception, not a deviation.

| Token | Value | Use for |
|---|---|---|
| `--fg-1` | `#191c1e` | Primary text — headings, names, emphasized cells |
| `--fg-2` | `#434655` | Body / secondary text |
| `--fg-3` | `#515f74` | Tertiary text — captions, meta, hints, table secondary columns |
| `--fg-4` | `#a0a4af` | Disabled text (rare — most "muted" cases use `--fg-3`) |
| `--primary` | `#004ac6` | Brand blue — links, icon-on-accent, focus accents, `text-[var(--primary)]` |
| `--bg-page` | `#f7f9fb` | App background, zebra hover row (`hover:bg-[var(--bg-page)]`) |
| `--bg-card` / white | `#ffffff` | Card / dialog / row surfaces |
| `--bg-muted` | `#f2f4f6` | Table header background, secondary surface, inactive nav bg |
| `--bg-accent` | `#dbe1ff` | Selected nav row, accent badges, active picker background |
| `--bg-input` | `#e6e8ea` | Disabled input background |
| `--destructive` | `#ba1a1a` | Danger buttons/text (also raw `#93000a`/`#ffdad6` for the banner recipe below) |
| `--ring` | `#2563eb` | Focus rings |

**Hairline strokes** — always the same rgba, never a solid gray:
`ring-[rgba(195,198,215,0.30)]` (cards/rows), `border-[rgba(195,198,215,0.20)]`
(dividers), `border-[rgba(195,198,215,0.15)]` (table row separators, lighter
than the card ring), `border-[rgba(195,198,215,0.40)]` (dashed empty-state
border, outline badge border).

**Semantic status colors** — always the hardcoded pair (bg + fg), not the
shadcn `--destructive`/`--success` tokens, for status pills and banners:

| Status | Background | Foreground |
|---|---|---|
| Success / active | `#d1fae5` | `#065f46` |
| Warning | `#fef3c7` | `#78350f` (or `#b45309`) |
| Danger / inactive | `#ffdad6` | `#93000a` |

**Gotcha — `--muted` is not `--bg-muted`**: shadcn ships its own `--muted`
(`#eceef0`, dark-mode-aware) alongside SigDoc's semantic `--bg-muted`
(`#f2f4f6`). They're visually close but NOT the same token — always use
`var(--bg-muted)` for SigDoc surfaces (table headers, secondary backgrounds).
`var(--muted)` slipping into a `className` is a deviation, not a legitimate
alternate.

**Computed-variable violet** (new — see §12) — tokenized as `--fg-computed:
#5b21b6` in `index.css`, paired with the existing `.var-chip-computed` class
(`background: linear-gradient(135deg, #ede9fe, #ddd6fe); border: 1px solid
#a78bfa;`). Any inline (non-chip) text that refers to a computed/auto value
must use `text-[var(--fg-computed)]`, never a raw `#5b21b6`.

---

## 2. Typography scale

Sizes actually used in the codebase (bracketed arbitrary values — Tailwind's
default scale is NOT used for body/meta text):

| Size | Class | Where |
|---|---|---|
| 22px | `text-[22px]` | Page-level entity title (template detail `<h1>`) |
| 20px | `text-xl` | **Dialog title** (bold) — see §4 |
| 18px | `text-lg` | Section/tab heading (`<h3>` inside a tab, e.g. "Datos guardados") |
| 15px | `text-[15px]` | Emphasized mono value (active variable name in editor) |
| 14px | `text-sm` / `text-[14px]` | Body text, table cell primary text, document preview paragraph |
| 13.5px | `text-[13.5px]` | Dense body copy (banners, confirmation prose) |
| 13px | `text-[13px]` | Secondary card copy, banner text, document paragraph in editor |
| 12.5px | `text-[12.5px]` | Small — dense field labels, tab subtitles, list secondary line |
| 12px | `text-xs` / `text-[12px]` | Badge text, `sd-meta` uppercase eyebrow, table header |
| 11.5px | `text-[11.5px]` | Mono email/id captions, hint text, chip text |
| 11px | `text-[11px]` | Tiny — field hint paragraphs, table header uppercase label |
| 10.5px | `text-[10.5px]` | Micro count/status pill inside a dense list (sidebar counts, tab badges) |

Rule of thumb: **mono font (`font-mono`) for anything that is data, not
prose** — emails, variable names/placeholders, ids.

**List-page header** (top of a resource's index page, e.g. `/usuarios`,
`/plantillas`): `<h2 className="text-2xl font-bold tracking-tight
text-[var(--fg-1)]">` + `<p className="text-sm text-[var(--fg-3)]">` for the
subtitle, optionally preceded by an `sd-meta` eyebrow line (`UsersPage` is the
canonical reference). This is distinct from the `text-[22px]` entity-detail
`<h1>` above — index pages use `text-2xl` (24px), a single record's detail
page uses `text-[22px]`.

**Two legitimate `<h3>` section-heading sizes — don't conflate them**:
1. **Tab-root heading** (sits directly on the tab/page background, no card
   wrapper around it; a separate card/table follows below): `text-lg`. E.g.
   `PresetsTab`'s "Datos guardados", `TemplateDetail`'s "Historial de
   versiones".
2. **Card-internal header title** (lives inside the header row of a single
   unified `bg-white` card that also contains the body — table/list rows
   directly below, same card, no gap): `text-base`. E.g. `DocumentsTab`,
   `SharesTab`, `DocumentList`, `DynamicForm`'s "Complete las variables".
   This card variant also legitimately skips the ring
   (`shadow-[var(--shadow-md)]` alone, no `ring-1`) — don't "fix" it to add
   one; it's a different, consistently-used recipe from the table-wrapper
   card in §3/§8, not a deviation.

---

## 3. Card / container recipe

The one true "elevated surface" recipe, copied verbatim everywhere (table
wrapper, list rows, editor panels, stat cards):

```
rounded-xl bg-white shadow-[var(--shadow-sm)] ring-1 ring-[rgba(195,198,215,0.30)]
```

- Use `shadow-[var(--shadow-md)]` instead of `-sm` for `<Card>`-based content
  blocks that sit directly on the page background without competing rows
  (e.g. `Card` info panels in `TemplateDetail`'s "Información" tab) —
  `border-0 bg-white shadow-[var(--shadow-md)]`.
- Interactive/hoverable cards (e.g. `TemplateCard`) add
  `transition-all duration-150 hover:-translate-y-0.5 hover:shadow-[var(--shadow-md)] hover:ring-[rgba(37,99,235,0.30)]`.
- Nested dividers inside a card use the lighter hairline:
  `border-t border-[rgba(195,198,215,0.15)]` (row-to-row) or `0.20` (section-to-section).
- Small icon badges inside cards: `inline-flex size-8..size-11 items-center
  justify-center rounded-lg` (or `rounded-full` for avatars) with
  `bg-[var(--bg-accent)] text-[var(--primary)]` (neutral) or the brand
  gradient (identity avatars — see §7).

---

## 4. Dialog anatomy

Structure (always, via `@/components/ui/dialog`):

```tsx
<Dialog open={open} onOpenChange={onOpenChange}>
  <DialogContent className="sm:max-w-md"> {/* sm | md | lg | 2xl | 4xl by content */}
    <form onSubmit={handleSubmit}> {/* only if the body is a form */}
      <DialogHeader>
        <DialogTitle className="text-xl font-bold tracking-tight">…</DialogTitle>
        <DialogDescription>…</DialogDescription>
      </DialogHeader>
      <div className="flex flex-col gap-4 py-4">{/* body */}</div>
      <DialogFooter>
        <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
          Cancelar
        </Button>
        <Button type="submit" disabled={...} className="bg-gradient-to-br from-[#004ac6] to-[#2563eb] font-semibold text-white shadow-[var(--shadow-brand-sm)] hover:shadow-[var(--shadow-brand-md)] disabled:opacity-60">
          {isPending ? (<><LoaderCircle className="mr-2 size-4 animate-spin" />Guardando...</>) : (<><Check className="mr-2 size-4" />Guardar cambios</>)}
        </Button>
      </DialogFooter>
    </form>
  </DialogContent>
</Dialog>
```

**Rules:**

- `DialogTitle` is **always** `className="text-xl font-bold tracking-tight"`.
  The shadcn default (`text-base font-medium`, no override) is NOT the
  SigDoc convention — every dialog in the app overrides it. (Fixed across
  the folder/preset/rename dialogs in this pass — see the findings table.)
- Cancel is always `variant="outline"`, always first, always closes without
  side effects.
- The primary/confirm action is always **last** (right-most), always the
  brand gradient for a creative/save action, or solid `bg-[var(--destructive)]
  hover:bg-[#93000a]` for a destructive confirm.
- Pending labels always end in an ellipsis: `"Guardando..."` / `"Creando..."`
  (ASCII triple-dot) for verbs with a spinner, or a real `…` character
  (`"Desactivando…"`, `"Eliminando…"`, `"Subiendo…"`) — both forms exist in
  the shipped codebase; either is acceptable, just be consistent **within a
  single component**. Never a bare verb with no trailing punctuation while
  pending.
- A `LoaderCircle` spinner (`className="mr-2 size-4 animate-spin"`) accompanies
  the pending label whenever the button has room for one; icon-only/compact
  confirm buttons (e.g. an inline row's "Confirmar") may fall back to a bare
  `"…"` glyph instead.
- Confirm-by-typing destructive dialogs (delete/deactivate) show the exact
  phrase in `<span className="font-mono text-[var(--destructive)]">FRASE</span>`
  and gate the submit button on an exact string match.

### Field label recipe — two legitimate variants

1. **Eyebrow label** (default — use this unless the dialog matches case 2):
   `text-xs font-semibold uppercase tracking-[0.04em] text-[var(--fg-3)]`.
   Used by every users-feature dialog and by simple 1–2 field utility dialogs
   (create/rename folder, move to folder, save preset).
2. **Dense field label** (only for panels/dialogs that render a field **per
   dynamic data item**, e.g. one input per template variable): compact,
   non-uppercase — `text-[12.5px] font-medium text-[var(--fg-2)]`. Uppercasing
   N stacked labels for arbitrary variable names in `VariablesTab`'s computed
   config grid or `PresetFormDialog`'s per-variable inputs adds visual noise
   without adding information — this is an intentional, documented exception,
   not a deviation. Do not "fix" it to the eyebrow style.

---

## 5. Button variants

`@/components/ui/button` ships `default | outline | secondary | ghost |
destructive | link`, but SigDoc's actual primary action is **not** the plain
`default` variant — it's the brand gradient, applied via `className` on top
of the base button:

```
bg-gradient-to-br from-[#004ac6] to-[#2563eb] font-semibold text-white shadow-[var(--shadow-brand-sm)] hover:shadow-[var(--shadow-brand-md)]
```

Use this for: dialog primary submit, page-level primary CTA (Crear Usuario,
Nueva carpeta submit, Generar Documento), never for a secondary action.

| Intent | Variant | Notes |
|---|---|---|
| Primary / create / save | gradient (above) | `disabled:opacity-60` when the dialog can be submitted while invalid-but-not-blocked |
| Secondary / cancel / alternate | `variant="outline"` | Default choice for anything not primary and not destructive |
| Tertiary / row-level toggle | `variant="ghost"` | Icon buttons in tables/lists (`size="icon-sm"`), view-mode toggles |
| Destructive confirm | `className="bg-[var(--destructive)] font-semibold text-white hover:bg-[#93000a]"` | NOT the shadcn `variant="destructive"` (a soft red-on-light chip) — that variant is reserved for low-emphasis destructive hints, not a confirming action button |
| Destructive row action (icon) | `variant="ghost"` + `className="text-[var(--fg-2)] hover:bg-[#ffdad6]/50 hover:text-[var(--destructive)]"` | Hover reveals intent without a permanently red icon |
| Destructive outline (labeled, header-level) | `variant="outline"` + `className="border-[rgba(186,26,26,0.25)] text-[var(--destructive)] hover:bg-[#ffdad6]/50 hover:text-[var(--destructive)]"` | e.g. "Eliminar" in a template's action row |

Icon-only buttons always use `size="icon-sm"` (28px) in tables/lists;
`size="sm"` for labeled row actions.

---

## 6. Badge / chip recipes

| Recipe | Class | Use |
|---|---|---|
| Role pill (admin) | `bg-gradient-to-br from-[#004ac6] to-[#2563eb] text-white border-0 rounded-full` | Highest-privilege role only |
| Role pill (elevated, non-admin) | `bg-[var(--bg-accent)] text-[var(--primary)] border-0 rounded-full` | e.g. template_creator |
| Role pill (base) | `bg-[var(--bg-muted)] text-[var(--fg-2)] border-0 rounded-full` | Lowest-privilege role |
| Status — active/success | `rounded-full border-0 bg-[#d1fae5] text-[#065f46] hover:bg-[#d1fae5]` + a `size-1.5 rounded-full bg-[#065f46]` leading dot | "Activo", "Actual" |
| Status — inactive/danger | `rounded-full border-0 bg-[#ffdad6] text-[#93000a] hover:bg-[#ffdad6]` + matching dot | "Inactivo" |
| Outline/neutral info chip | `variant="outline"` + `rounded-full border-[rgba(195,198,215,0.40)] text-[var(--fg-3)]` | version tag suffix, folder chip, count-of-N |
| Accent info chip | `rounded-full border-0 bg-[var(--bg-accent)] text-[var(--primary)] hover:bg-[var(--bg-accent)]` | "Compartida" |
| Micro count/status pill (dense lists) | `rounded-full px-1.5 text-[10.5px] font-semibold` with `bg-white text-[var(--primary)]` (active row) / `bg-[var(--bg-muted)] text-[var(--fg-3)]` (inactive row) | sidebar folder counts, tab counts, "Auto"/"Pendiente" in the variables review panel |
| `.var-chip` family (mono, inline in prose) | see §12 | Placeholder / active-variable / muted-variable / computed-variable inline chips |

**When you need a new badge variant**: reuse the bg/fg *pair* pattern above
(soft background + matching darker foreground, `rounded-full`, `border-0`) —
never introduce a single new saturated color without pairing a soft
background token with it.

---

## 7. Avatar / identity chip

```
inline-flex size-9..size-11 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-[#004ac6] to-[#2563eb] text-[11px]..text-[13px] font-semibold text-white
```
Initials only (2 chars max), derived from email local-part or full name.
Scale the size/font together: `size-9`/`text-[11px]` in table rows,
`size-10`/`text-[12px]` in compact dialog identity cards, `size-11`/`text-[13px]`
in the primary "Editar usuario" identity card.

---

## 8. Table recipe (from `UserList`)

```tsx
<div className="overflow-hidden rounded-xl bg-white shadow-[var(--shadow-sm)] ring-1 ring-[rgba(195,198,215,0.30)]">
  <Table>
    <TableHeader>
      <TableRow className="border-b border-[rgba(195,198,215,0.2)] bg-[var(--bg-muted)] hover:bg-[var(--bg-muted)]">
        <TableHead className="font-semibold text-[var(--fg-1)]">Columna</TableHead>
        {/* last actions column: */}
        <TableHead className="w-[120px] text-right font-semibold text-[var(--fg-1)]">Acciones</TableHead>
      </TableRow>
    </TableHeader>
    <TableBody>
      <TableRow className="border-b border-[rgba(195,198,215,0.1)] transition-colors hover:bg-[var(--bg-page)]">
        <TableCell className="py-3">…</TableCell>
      </TableRow>
    </TableBody>
  </Table>
</div>
```

- Header row: muted background, semibold `--fg-1` text, no hover-state change.
- Body rows: lighter hairline (`0.1` opacity) than header (`0.2`), hover tints
  to `--bg-page`.
- Actions column is always right-aligned, `w-[80..120px]`, icon-only ghost
  buttons.
- **Search row** above the table: `relative w-full max-w-sm` wrapping an
  `Input` with `pl-9` and an absolutely-positioned `Search` icon
  (`absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-[var(--fg-3)]`),
  plus a right-aligned `text-xs text-[var(--fg-3)]` "N de M" counter.
- **Pager** (when total > page size): its own card —
  `flex items-center justify-between rounded-xl bg-white px-4 py-3
  shadow-[var(--shadow-sm)] ring-1 ring-[rgba(195,198,215,0.30)]` with
  `variant="outline" size="sm"` Anterior/Siguiente buttons and a
  `text-xs font-medium text-[var(--fg-2)]` "Página X de Y" label.

---

## 9. Error / info / warning banner recipe

Always the hardcoded bg/fg pair (never `border-destructive/50 bg-destructive/5`
shadcn utilities — that pattern exists in a couple of older, not-yet-migrated
spots and is NOT the target recipe):

```
rounded-[10px] bg-[#ffdad6] px-3.5 py-3 text-[13px] leading-[1.45] text-[#93000a]
```

with a leading icon (`CircleAlert`, `mt-px size-4 shrink-0`) when the message
needs a strong visual anchor. Info banners swap the palette to
`bg-[var(--bg-accent)] ... text-[var(--primary)]` (with `Info`/`BookOpen`
icons). Compact inline info banners lower the padding to `py-2.5` and text to
`text-[12.5px]`.

---

## 10. Empty-state recipes — two legitimate variants

1. **"No results for current filter"** (search/filter emptied a list that
   otherwise has items): dashed border, no elevation —
   `flex flex-col items-center justify-center rounded-xl border border-dashed
   border-[rgba(195,198,215,0.4)] bg-white/50 p-12 text-center` with a single
   `text-[var(--fg-2)]` paragraph.
2. **"Nothing here yet"** (the collection is genuinely empty): a `Card`
   (`border-0 bg-white shadow-[var(--shadow-md)]`) with `CardContent
   className="pt-6"`, a primary `text-[var(--fg-2)]` line and a secondary
   `text-sm text-[var(--fg-3)]` hint that names the CTA (`<strong>Nuevo</strong>`).

Don't merge these — they signal different things to the user (try a
different search vs. go create something).

---

## 11. Toast conventions

Via `sonner`, always through `toast.success/error/info` — never a custom
toast component. Success messages are past-tense declarative sentences
("Usuario actualizado con éxito", "Carpeta creada con éxito"). Errors prefer
the backend's `response.data.detail` string, falling back to a generic
Spanish message ("Error al actualizar usuario"). Info is used sparingly for
no-op guards ("No hay cambios para guardar").

---

## 12. Variable chips (`.var-chip` family) — `index.css`

Defined once in `index.css`, reused by both the Variables tab's
`ParagraphPreview` and the full document editor's `PlaceholderPill`:

| Class | Look | Meaning |
|---|---|---|
| `.var-chip` | base — mono, `11.5px`, `500` weight, `padding: 1px 6px`, `radius: 6px` | applied to every chip alongside a modifier |
| `.var-chip-active` | amber gradient bg, `#78350f` text, amber border+shadow, `600` weight | the variable currently selected/being edited, or filled in the live editor |
| `.var-chip-muted` | `--bg-muted` bg, `--fg-3` text, hairline border | any other variable in the same context |
| `.var-chip-computed` | violet gradient bg (`#ede9fe → #ddd6fe`), `var(--fg-computed)` text, `#a78bfa` border | server-owned/auto-calculated variable — never clickable, never editable (`cursor-default`) |

**Rule**: any UI that needs to render an inline, mono, pill-shaped reference
to a template variable — active, muted, or computed — uses one of these
classes. Don't hand-roll a new inline chip with ad hoc Tailwind utilities.
If you need the computed-violet color **outside** a chip (e.g. a plain text
label), reference the `--fg-computed` custom property, not a raw hex.

---

## 13. Icon sizing

| Context | Size |
|---|---|
| Inline with 11–13px text (chip icons, badge icons) | `size-3` |
| Inline with 12.5–14px text (buttons, row icons, labels) | `size-3.5` (the default) |
| Standalone row-action icon buttons | `size-4` |
| Card header icon badges | `size-4` inside a `size-8..size-11` container |
| Empty-state / large decorative icons | `size-5` to `size-8` |

Icons always inherit color via `text-[...]` on the wrapping element — never
hardcode a `fill`/`stroke` on the `<svg>` itself.

---

## 14. Spacing rhythm

- Dialog body fields: `flex flex-col gap-4` (field groups) → `grid gap-1.5`
  (label + input pairs) → `grid gap-3 sm:grid-cols-2` (paired fields).
- List rows / stacked cards: `gap-2` to `gap-2.5`.
- Card internal padding: `p-3` to `p-4` for compact cards, `p-5` for
  primary content cards.
- Page-level section spacing: `space-y-4` (tab content) to `space-y-5`
  (page root).

---

## 15. Focus / hover states

- Interactive rows/buttons: `transition-colors` (or `transition-all` when
  also animating shadow/transform), hover tint moves toward `--bg-page` or
  `--bg-muted` for neutral rows, toward the semantic color's soft background
  for destructive/accent actions (`hover:bg-[#ffdad6]/50`, `hover:bg-[var(--bg-accent)]/60`).
- Focus-visible: rely on the shared `Button`/`Input`/`Select` primitives'
  built-in `focus-visible:ring-3 focus-visible:ring-ring/50` — don't override
  unless the element is a hand-rolled `<button>` (then add
  `focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]`).
- Card lift on hover (only for clickable cards, not rows): `hover:-translate-y-0.5
  hover:shadow-[var(--shadow-md)] hover:ring-[rgba(37,99,235,0.30)]`.

---

## Copy register (Spanish)

- Neutral, professional Spanish — no regional slang, no *voseo* in UI copy.
- Sentence case for labels/titles ("Nueva carpeta", not "Nueva Carpeta") —
  except historically-established title-case CTAs kept for continuity
  ("Crear Usuario", "Generar Documento", "Generación Masiva") — don't
  "fix" those, they're an accepted legacy exception, not a new pattern to
  copy.
- Pending states end in an ellipsis (see §4).
- Error copy is specific and actionable ("El correo no puede modificarse."),
  never a bare "Error."
- Use `«guillemets»` for user-entered names quoted back in a toast/message
  (`` `Datos «${preset.name}» eliminados` ``).
