---
name: Requirement AI
description: A reading surface with a dashboard's frame, for turning raw business requirements into an approved, traceable backlog.
colors:
  canvas: "#f6f6f3"
  surface: "#ffffff"
  surface-sunken: "#ecece7"
  surface-raised: "#ffffff"
  ink: "#14171a"
  ink-soft: "#3a4047"
  ink-muted: "#5b646d"
  ink-faint: "#656d76"
  line: "#dcdcd5"
  line-strong: "#85857e"
  accent: "#4338ca"
  accent-strong: "#352ba3"
  accent-wash: "#edebfb"
  on-accent: "#ffffff"
  success: "#136b45"
  success-wash: "#e3f1e9"
  warning: "#8a4b08"
  warning-wash: "#faefdf"
  warning-edge: "#b96b12"
  danger: "#b3231d"
  danger-wash: "#fae6e4"
typography:
  display:
    fontFamily: "Public Sans, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1.75rem"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "-0.01em"
  headline:
    fontFamily: "Public Sans, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1.25rem"
    fontWeight: 600
    lineHeight: 1.3
  title:
    fontFamily: "Public Sans, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 600
    lineHeight: 1.4
  body:
    fontFamily: "Public Sans, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.5
  document:
    fontFamily: "Source Serif 4, ui-serif, Georgia, serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.6
  document-lead:
    fontFamily: "Source Serif 4, ui-serif, Georgia, serif"
    fontSize: "1.125rem"
    fontWeight: 400
    lineHeight: 1.55
  label:
    fontFamily: "Public Sans, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: "0.04em"
  meta:
    fontFamily: "Public Sans, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.8125rem"
    fontWeight: 400
    lineHeight: 1.45
  mono:
    fontFamily: "IBM Plex Mono, ui-monospace, Consolas, monospace"
    fontSize: "0.8125rem"
    fontWeight: 400
    lineHeight: 1.5
rounded:
  xs: "3px"
  sm: "6px"
  md: "10px"
  lg: "16px"
  full: "999px"
spacing:
  "1": "4px"
  "2": "8px"
  "3": "12px"
  "4": "16px"
  "5": "20px"
  "6": "24px"
  "8": "32px"
  "10": "40px"
  "12": "48px"
  "16": "64px"
components:
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.on-accent}"
    typography: "{typography.body}"
    rounded: "{rounded.sm}"
    padding: "8px 16px"
    height: "36px"
  button-primary-hover:
    backgroundColor: "{colors.accent-strong}"
    textColor: "{colors.on-accent}"
  button-secondary:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: "8px 16px"
    height: "36px"
  button-danger:
    backgroundColor: "{colors.danger}"
    textColor: "{colors.on-accent}"
    rounded: "{rounded.sm}"
    padding: "8px 16px"
    height: "36px"
  button-text:
    backgroundColor: "transparent"
    textColor: "{colors.accent}"
    typography: "{typography.body}"
    padding: "0 4px"
    height: "24px"
  input:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.sm}"
    padding: "8px 12px"
    height: "36px"
  card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink-soft}"
    rounded: "{rounded.md}"
    padding: "24px"
  card-inset:
    backgroundColor: "{colors.surface-sunken}"
    rounded: "{rounded.md}"
    padding: "24px"
  badge-attention:
    backgroundColor: "{colors.warning-wash}"
    textColor: "{colors.warning}"
    typography: "{typography.label}"
    rounded: "{rounded.sm}"
    padding: "4px 8px"
  pill-active:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.on-accent}"
    typography: "{typography.meta}"
    rounded: "{rounded.full}"
    padding: "4px 12px"
    height: "32px"
---

# Design System: Requirement AI

<!-- Derived from the shipped code at the end of redesign Phase 0: frontend/src/styles/tokens.css,
     the @theme bridge in frontend/src/styles/index.css, and frontend/src/components/ui/.
     docs/design-system.md is the full rationale and measurement record; this file is the
     applied summary. Screens not yet redesigned (docs/ux-plan.md Phases 1–9) still carry older
     layouts; where they disagree with this file, this file wins. -->

## Overview

**Creative North Star: "The Working Paper"**

A reading surface with a dashboard's frame. The interface is the desk; the requirement is the paper on it. The real work here is a person reading a document carefully, marking what is uncertain, and signing something, so the frame is dense and instrumented — tables, filters, sticky headers, counts — while the content it holds is set like a document: a generous measure, high contrast, nothing decorative and nothing moving.

Chrome recedes and content does not. Navigation, rails and toolbars sit on a quiet paper ground separated by hairlines, never by shadow; the panels that hold a requirement, a finding or a story get the full white sheet and the larger serif. The only loud thing on a screen is the unresolved thing: one indigo accent spent on the next action, and the attention and blocking states carried by colour *and* an edge *and* words. Nothing pretends to be finished — generated content carries its provenance, unapproved content its state, stale content says so.

It is not a glass, neumorphic or gradient surface; not an OLED-black dark theme; not a marketing page; not a consumer app. No illustration, no photography, no decorative iconography.

**Key Characteristics:**
- Warm paper neutrals, one indigo accent, three reserved status hues.
- Two reading registers: Public Sans for the instrument, Source Serif 4 for the document.
- Flat in flow; shadow only for layers that genuinely float, and always with a border.
- A 3px left edge is the one emphasis device.
- Paper (light) and Slate (dark) themes, both measured to WCAG 2.2 AA.

## Colors

Quiet ground, loud state: neutrals do all the structural work, and colour appears only where it carries a status, a provenance or the single next action.

### Primary
- **Signal Indigo** (`accent`): the next action, the current step, the thing waiting on a person — and links. Chosen by elimination: green, amber and red are spent on status, so indigo is the one hue that is unmistakably not one. In Slate it lifts to #a9a2ff.
- **Deep Indigo** (`accent-strong`): hover and pressed on anything filled with Signal Indigo.
- **Indigo Wash** (`accent-wash`): the ground of the current step in the stage rail and the active sidebar item. Never provenance, never decoration.
- **On Indigo** (`on-accent`): text and glyphs on an indigo fill. In Slate this is the near-black #15122b, not white — white on the lifted indigo measures 2.26:1.

### Neutral
- **Working Paper** (`canvas`): the page ground behind everything.
- **Clean Sheet** (`surface`): panels, cards, table bodies, fields — where content lives.
- **Margin Grey** (`surface-sunken`): rails, insets, table headers, the reference register, skeletons. Darker than the sheet in *both* themes.
- **Raised Sheet** (`surface-raised`): dialogs, drawers, popovers, toasts. In Slate it is a step lighter than the surface, because there the tone step *is* the elevation.
- **Pressed Ink** (`ink`), **Graphite** (`ink-soft`), **Pencil** (`ink-muted`), **Faint Pencil** (`ink-faint`): read-this-first, secondary prose, metadata, and the floor. Nothing lighter than Faint Pencil carries text in either theme.
- **Hairline** (`line`): decorative dividers *inside* a bounded surface.
- **Rule Line** (`line-strong`): the boundary of anything a person operates — inputs, secondary buttons, filter pills. It clears 3:1 where Hairline does not.

### Status
- **Approved Green** (`success`) on **Green Wash** (`success-wash`): approved, ready. Always with a check glyph.
- **Attention Amber** (`warning`) on **Amber Wash** (`warning-wash`), edged with **Amber Edge** (`warning-edge`): uncertainty, staleness, unresolved findings, unsaved work — the product's most important state. Amber Edge is non-text only.
- **Blocking Red** (`danger`) on **Red Wash** (`danger-wash`): blocks confirmation, errors, destructive confirmation.

### Named Rules
**The One Accent Rule.** Signal Indigo is spent once per screen, on the next action or the current step. Two accents on a screen means one of them is wrong; there is no secondary brand colour and no separate CTA colour.

**The Reserved Vocabulary Rule.** Green, amber and red mean approved, attention and blocking — everywhere, including charts. A green bar that means "Q3" is a defect.

**The Two Channels Rule.** No status is shown by colour alone: every one also carries a glyph, a 3px edge or words. Provenance is a glyph plus a label ("Generated", "Edited"), never a tint.

**The Tokens Only Rule.** No component names a hex, an `rgb()` or a bare `white`; `styles/palette.test.ts` fails the build if one appears outside `tokens.css`.

## Typography

**Interface Font:** Public Sans (with ui-sans-serif, system-ui)
**Document Font:** Source Serif 4 (with ui-serif, Georgia)
**Machine Font:** IBM Plex Mono (with ui-monospace, Consolas)

**Character:** a deliberately characterless, heavily tested grotesque for a dense instrument, beside a serif drawn for reading paragraphs of careful prose — so a person can tell peripherally whether they are looking at the product or at the requirement. All three are self-hosted: offline operation is a first-class mode.

### Hierarchy
- **Display** (700, 1.75rem, 1.2, -0.01em): the page `h1`, which is the requirement's own title — one per page.
- **Headline** (600, 1.25rem, 1.3): section and panel headings.
- **Title** (600, 1rem, 1.4): card headings — an Epic, a Feature, a finding group.
- **Body** (400, 0.875rem, 1.5): interface prose, table cells, helper text; capped at 80ch.
- **Document** (Source Serif 4, 400, 1rem, 1.6): all requirement and generated prose; capped at 68ch.
- **Document lead** (Source Serif 4, 400, 1.125rem, 1.55): the business need as first written.
- **Label** (600, 0.75rem, 0.04em): field labels and column headers, in sentence case.
- **Meta** (400, 0.8125rem, 1.45): timestamps, owners, counts, with tabular numerals.
- **Mono** (IBM Plex Mono, 400, 0.8125rem): requirement IDs, checksums, fingerprints — nothing else.

### Named Rules
**The Sentence Case Rule.** Labels are sentence case. Uppercase survives in exactly one place, the `NEXT` marker, where it is a symbol rather than a word.

**The Register Rule.** Serif means "this is document content", whoever wrote it. It is not the provenance signal.

**The Floor Rule.** 14px is the interface floor and 16px the document floor; nothing renders below 12px, badges included. No light weights.

## Layout

One frame on every route. A fixed 56px header carries the brand, search, notifications, help, account and the primary action — and no navigation row. A 240px sidebar, collapsible to 56px icons and persisted, is the only global navigation: Requirements, Documents, Activity, Reports. Inside a requirement, a six-step stage rail (Source, Clarify, Knowledge, Confirm, Backlog, Review & approve) sits beside the work. The main column tops out at 1360px with 40px side padding, 24px at `md` and below; prose inside it is capped at 68ch.

Spacing is a 4px grid with ten steps — 4, 8, 12, 16, 20, 24, 32, 40, 48, 64 — and nothing between them. Controls are 36px (32px compact), table rows 44px, and every target is at least 24×24. Three density registers are applied by context and never mixed inside one panel: chrome (32–36px rows, 13px type), table (44px rows, 14px), document (auto rows, serif at 16px/1.6).

Three breakpoints and only three: `sm` 640px (headings stack, cards go full width), `md` 900px (the sidebar becomes a drawer, two columns become one), `lg` 1050px (the widest multi-pane layouts fold). A fourth is a defect, and `styles/breakpoints.test.ts` says so. Desktop is the real usage scene; narrow widths must not break, but no flow is designed for a phone.

Stacking comes from one scale — base 1, sticky 10, chrome 20, overlay 40, top 50 — enforced by `styles/layers.test.ts`. Every scroller under the fixed header clears it with `scroll-padding-top`, so a focused control never lands beneath it.

## Elevation & Depth

Anything in the document flow is flat: a 1px hairline and a half-step of surface tone do all the separating. Shadow is reserved for layers that genuinely float, it is always paired with a 1px border, and in the Slate theme the lighter raised surface does most of the work because a shadow on a dark ground carries almost nothing.

### Shadow Vocabulary
- **Hover lift** (`--elev-1`: `0 1px 2px rgb(20 23 26 / .06), 0 2px 8px rgb(20 23 26 / .06)`): an interactive card or row under the pointer.
- **Popover** (`--elev-2`: `0 4px 12px rgb(20 23 26 / .10)`): dropdowns, menus, the notification and saved-view popovers.
- **Drawer** (`--elev-3`: `0 12px 28px rgb(20 23 26 / .14)`): Source, People, evidence, and the narrow-screen navigation.
- **Modal** (`--elev-4`: `0 20px 48px rgb(20 23 26 / .18)`): dialogs and the toast stack.

### Named Rules
**The Flat Flow Rule.** Nothing in the flow casts a shadow, and no button ever does — buttons answer hover with colour, never with lift.

**The One Edge Rule.** The 3px left edge is the single emphasis device: Signal Indigo for the current or next thing, a status colour for a flagged one. No glows, no heavy outlines, no colour-filled panels.

## Shapes

Softer than an institutional 2/4/8 ladder, and still restrained. Five radii, nothing between them: 3px for status marks and selection outlines, 6px for buttons, inputs, chips and badges, 10px for cards, panels, rails and empty states, 16px for dialogs, drawers, popovers and toasts, and a full round for filter pills, avatars, step numbers and counts. An inner radius is the outer radius minus its padding, floored at 6px — a control inside a card stays 6px. A drawer rounds only its open edge; the other is flush with the viewport. Borders are 1px throughout; weight comes from the 3px edge, never from a thicker frame. An empty state is the one dashed border.

## Components

Sturdy and legible before elegant, and built to WCAG 2.2 AA at the primitive so no screen has to remember.

### Buttons
- **Shape:** gently rounded (6px), 36px tall, 8px × 16px padding, label written as the act in sentence case ("Save and analyse business need").
- **Primary:** Signal Indigo fill with On Indigo text; hover moves to Deep Indigo. The focus ring inverts and insets on the fill.
- **Secondary:** transparent, 1px Rule Line border, Pressed Ink text; hover mixes 10% indigo into the ground (lighter in Slate, never darker).
- **Ghost:** no border until hover. **Danger:** Blocking Red fill, for destructive confirmation only.
- **Text:** underlined Signal Indigo, 24×24 minimum — Cancel, Retry, Mark read. A red variant exists for small destructive acts.
- **States:** a gated primary action stays visible and explains itself underneath; an async action disables and says what is running. Hover changes colour only.

### Chips
- **Badge:** 6px radius, no border, 12px/600 label on a status wash, always with its glyph.
- **Filter pill:** fully round, Clean Sheet with a Rule Line border; active is filled Signal Indigo. Only statuses with a count render.

### Cards / Containers
- **Corner Style:** 10px.
- **Background:** Clean Sheet, or Margin Grey when inset.
- **Shadow Strategy:** flat; an interactive card takes the hover lift.
- **Border:** 1px Hairline; a status card adds the 3px left edge and the matching wash.
- **Internal Padding:** 24px.

### Inputs / Fields
- **Style:** Clean Sheet ground, 1px Rule Line, 6px radius, 36px tall, a real label above in Label type — never a placeholder standing in for one. Placeholders are worked examples.
- **Focus:** border to Signal Indigo plus the global ring.
- **Error / Disabled:** `aria-invalid` doubles the border in Blocking Red with an inset line (no layout shift) and the message sits below the field, linked by `aria-describedby`; disabled is Faint Pencil on Margin Grey.

### Navigation
- **Sidebar:** 240px on Margin Grey with a Hairline right edge; the active destination takes the Indigo Wash ground and a 3px Signal Indigo edge. Collapses to 56px icons; below `md` it becomes a 288px drawer from the left.

### Stage Rail (signature)
Six vertical steps. Complete: an Approved Green check and the step in Pressed Ink. Current: Indigo Wash ground, 3px Signal Indigo edge, indigo label. Blocked: Faint Pencil with a hollow ring — still navigable, because the destination explains itself better than a disabled control can. Every state carries a glyph as well as a colour.

### Next Action (signature)
One per workspace: a bordered block with a 3px Signal Indigo edge, a small uppercase `NEXT` marker, and the action in the person's own words — "Answer 4 blocking questions". The only element allowed to tell somebody what to do.

### Dialogs, drawers, toasts, loading
One modal primitive: traps focus, closes on Escape, returns focus to its trigger, is named by its heading, and sits on the Raised Sheet with a border over the scrim. Toasts stack bottom-left, four at most, tone shown in their edge and icon only, and never the only place an error is reported. Loading is a skeleton that reserves its space and pulses (flattened under reduced motion); the one spinner in the system marks a running AI job, whose duration nobody knows.

## Do's and Don'ts

### Do:
- **Do** take every colour, radius, space, duration and layer from the tokens — `var(--…)` or the Tailwind utility that bridges it.
- **Do** separate in-flow surfaces with a 1px Hairline and a tone step; reserve `--elev-*` for layers that float, and give each a border.
- **Do** mark the current or next thing with the 3px Signal Indigo edge, and a flagged thing with its status edge plus words.
- **Do** set requirement and generated prose in Source Serif 4 at 16px/1.6, capped at 68ch.
- **Do** make the unresolved and the blocking the most legible things on the screen.
- **Do** use the primitive's props (`variant`, `size`, `side`, `tone`) rather than a class that sets the same property — a competing class wins or loses by Tailwind's output order, not by intent.
- **Do** verify in Paper and Slate: text at 4.5:1, boundaries and focus at 3:1.

### Don't:
- **Don't** add a second accent, a CTA colour, or an amber or orange call to action — amber is the attention state.
- **Don't** put a shadow on anything in the flow, or on any button, ever.
- **Don't** set labels in tracked uppercase; the `NEXT` marker is the one exception.
- **Don't** show a status by colour alone, or provenance by a wash alone.
- **Don't** use a radius, space, duration or z-index off its ladder, or a fourth breakpoint.
- **Don't** use pure black grounds or pure white text in Slate, or white text on the lifted indigo.
- **Don't** add illustration, photography, decorative gradients or glass.
- **Don't** let a raw enum string (`needs_answers`, `ready_for_review`) reach a person; it gets a label in business language.
