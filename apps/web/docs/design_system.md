# Construct Web Design System

Scope: visual tokens for `apps/web`. Light mode only. Audience: PhD-track researchers and biotech professionals. Direction: sterile-modern, restrained, sharp, and product-grade. The layout is the v2 three-pane workspace; this document covers the visual system only.

The code keeps the existing Tailwind accent token name `coral` for cascade compatibility. Its value is now the Construct green accent, not coral.

---

## 1. Color Palette

The palette is near-white, cool-neutral, and green-accented. Nothing is pure marketing white except elevated `paper`, and green is used selectively for primary actions, focus, brand accent, and active state.

### Surfaces

| Token | Hex | Usage |
| --- | --- | --- |
| `cream` | `#fbfbf8` | Primary app background. Near-white and paper-like, with just enough warmth to avoid clinical glare. |
| `paper` | `#fffffc` | Elevated card and panel surface. Cooler and cleaner than the previous warm paper. |

### Text

| Token | Hex | Usage |
| --- | --- | --- |
| `ink` | `#1f2320` | Primary text and deep UI marks. Slightly darker and cooler for sharper contrast. |
| `slate` | `#5f665f` | Secondary text, metadata, captions, and helper copy. Gray-green neutral, not warm taupe. |

### Accent

| Token | Hex | Usage |
| --- | --- | --- |
| `coral` | `#365f43` | Compatibility token for the primary green accent. Used for primary actions, focus rings, brand `AI`, key links, active borders, and loading indicators. |

### Supporting Neutrals

| Token | Hex | Usage |
| --- | --- | --- |
| `line` | `#e3e3dc` | Default 1px borders and dividers. Cool gray-leaning, low-contrast separation. |
| `line-strong` | `#c9cbc2` | Stronger borders, selected boundaries, and secondary controls. |
| `mist` | `#f0f1ec` | Subtle hover, inset, and selected-row fill. Cool neutral, not cream-tan. |

### Semantic Validation

PASS is distinct from the primary accent. WARN and FAIL stay serious and muted, tuned for the cooler surface stack.

| Token | Hex | Usage |
| --- | --- | --- |
| `sage` | `#6f7f68` | PASS. Muted gray-sage, deliberately softer than the brand green. |
| `honey` | `#a9782c` | WARN. Restrained amber/ochre, not bright yellow. |
| `clay` | `#7b3d45` | FAIL. Deep muted oxblood, used only for blocking or error states. |

---

## 2. Typography

Two families total: a tighter display sans for headings and Inter for body/UI.

### Families

- **Headings / brand:** `Inter Tight`, Google Fonts, via `--font-serif` for compatibility with existing `font-serif` classes.
- **Body & UI:** `Inter`, Google Fonts, via `--font-sans`.

The old Newsreader direction was too literary. Inter Tight gives the workspace a more precise, serious software feel while preserving the existing class structure.

### Type Scale

| Token | Size | Line height | Weight | Tracking | Used for |
| --- | --- | --- | --- | --- | --- |
| `display` | `2.25rem` | `1.1` | `650` | `-0.035em` | Rare large titles. |
| `h2` | `1.625rem` | `1.15` | `650` | `-0.03em` | Modal titles and major section heads. |
| `h3` | `1.25rem` | `1.2` | `650` | `-0.025em` | Panel headings and compact card titles. |
| `body` | `1rem` | `1.5` | `400` | inherited | Default reading text. |
| `small` | `0.875rem` | `1.43` | `400` | inherited | Dense metadata and helper copy. |
| `caption` | `0.75rem` | `1.3` | `550` | optional uppercase tracking | Labels, badges, and compact metadata. |

Base body copy uses a subtle `letter-spacing: -0.005em` for a crisper product texture.

---

## 3. Spacing Scale

4px base throughout. Named tokens reduce ad-hoc values.

| Token | Value |
| --- | --- |
| `2xs` | `4px` |
| `xs` | `8px` |
| `sm` | `12px` |
| `md` | `16px` |
| `lg` | `24px` |
| `xl` | `32px` |
| `2xl` | `48px` |
| `3xl` | `64px` |

Default controls should lean `px-sm py-xs` or `px-sm py-2xs`. Reserve `lg` padding for genuinely spacious content blocks, not every panel.

---

## 4. Border Radius

Sharper than the first visual pass. Buttons and inputs should feel rectangular, not soft.

| Token | Value | Used for |
| --- | --- | --- |
| `sm` | `4px` | Inputs, chips, selected rows, small buttons. |
| `md` | `6px` | Buttons, cards, panels, textareas. |
| `lg` | `8px` | Modals and floating surfaces. |
| `pill` | `9999px` | Status dots and validation/status pills only. |

---

## 5. Shadows

Cool and quiet. Borders do most separation; shadows should be barely perceptible.

| Token | Value | Usage |
| --- | --- | --- |
| `rest` | `0 1px 2px rgba(31, 35, 32, 0.04)` | Minimal elevation on controls or subtle cards. |
| `raised` | `0 2px 4px rgba(31, 35, 32, 0.05), 0 1px 1px rgba(31, 35, 32, 0.04)` | Main map card and selected elevated panels. |
| `floating` | `0 12px 24px rgba(31, 35, 32, 0.08), 0 2px 6px rgba(31, 35, 32, 0.05)` | Modals, menus, and sheets. |

---

## 6. Tailwind Mapping

Current `theme.extend` values in `apps/web/tailwind.config.ts`:

```ts
colors: {
  cream: "#fbfbf8",
  paper: "#fffffc",
  ink: "#1f2320",
  slate: "#5f665f",
  coral: "#365f43",
  line: "#e3e3dc",
  "line-strong": "#c9cbc2",
  mist: "#f0f1ec",
  sage: "#6f7f68",
  honey: "#a9782c",
  clay: "#7b3d45",
},
fontFamily: {
  serif: ["var(--font-serif)", "Inter Tight", "Inter", "ui-sans-serif", "system-ui", "sans-serif"],
  sans: ["var(--font-sans)", "Inter", "ui-sans-serif", "system-ui", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "Roboto", "sans-serif"],
},
fontSize: {
  display: ["2.25rem", { lineHeight: "1.1", fontWeight: "650", letterSpacing: "-0.035em" }],
  h2: ["1.625rem", { lineHeight: "1.15", fontWeight: "650", letterSpacing: "-0.03em" }],
  h3: ["1.25rem", { lineHeight: "1.2", fontWeight: "650", letterSpacing: "-0.025em" }],
  body: ["1rem", { lineHeight: "1.5" }],
  small: ["0.875rem", { lineHeight: "1.43" }],
  caption: ["0.75rem", { lineHeight: "1.3", fontWeight: "550" }],
},
borderRadius: {
  sm: "4px",
  md: "6px",
  lg: "8px",
  pill: "9999px",
},
boxShadow: {
  rest: "0 1px 2px rgba(31, 35, 32, 0.04)",
  raised: "0 2px 4px rgba(31, 35, 32, 0.05), 0 1px 1px rgba(31, 35, 32, 0.04)",
  floating: "0 12px 24px rgba(31, 35, 32, 0.08), 0 2px 6px rgba(31, 35, 32, 0.05)",
}
```

---

## 7. Annotation Palette

SeqViz feature colors are defined in `apps/web/lib/component-colors.ts`:

| Feature | Hex |
| --- | --- |
| promoter | `#365f43` |
| GOI | `#7b3d45` |
| terminator | `#1f2320` |
| ORI | `#a9782c` |
| marker | `#6f7f68` |
| MCS | `#556b74` |
| other | `#5f665f` |

These are intentionally muted so the plasmid map integrates with the interface instead of looking like a separate default visualization widget.
