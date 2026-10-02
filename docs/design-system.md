# Requirement AI — Design System

**Direction: Working Paper.**

**Status:** source of truth for *mechanics* in the UI/UX redesign. [`docs/ux-plan.md`](ux-plan.md) governs scope, screens, routes, information architecture and flows; where the two disagree, the plan wins ([`CLAUDE.md`](../CLAUDE.md), UI Redesign Rules). No code was changed to produce this document.

**Generated with** the `ui-ux-pro-max` skill — `--design-system` pass plus `style`, `typography`, `color` and `ux` domain searches — then reconciled against [`PRODUCT.md`](../PRODUCT.md) and [`docs/ux-plan.md`](ux-plan.md). Every contrast ratio quoted here was computed from the hex values in this document, not estimated.

---

## 0. How to read this document, and what it replaces

This is a **full identity reset**. `docs/ux-plan.md` §0 records the decision: palette, typeface and tone are all open, and the previously shipped "Standards Bureau" identity — Bureau Oxblood `#af101a`, Archivo Narrow, the cool-paper canvas — is no longer an input. This document therefore **replaces the previous version of itself in full**, and in particular:

| Previously | Now |
|---|---|
| §2 reconciled a generic generator against the shipped design | Void per `ux-plan.md` §0. Re-decided in §2 below against a blank identity. |
| §4.4 proposed **WCAG 2.1 AA** | **Superseded.** The bar is **WCAG 2.2 AA**, settled and binding (`PRODUCT.md` §Accessibility & Inclusion, `ux-plan.md` §0). See §13. |
| Dark mode was absent | **Specified here** in full. This closes `ux-plan.md` §6 open decision 5 — see §17. |
| `DESIGN.md` was the identity source of truth | `DESIGN.md` becomes an *output* of the finished redesign, rewritten from the shipped result. It is not an input to anything in this document. |

Division of labour:

| Question | Answer lives in |
|---|---|
| What screens exist, what is a user doing there, in what order do we rebuild? | `docs/ux-plan.md` |
| What does it look like, at what ratio, what size, what radius, how does it move? | **this document** |
| What does a token resolve to at runtime? | `frontend/src/styles/tokens.css` (after Phase 0) |
| What did the finished product turn out to be? | `DESIGN.md`, written last |

---

## 1. Inputs

What the design has to survive, taken from `PRODUCT.md` and `ux-plan.md` rather than assumed:

- **Authenticated workspace, no marketing surface.** There is no funnel, no hero, no acquisition path. `PRODUCT.md` forbids fabricated logos, testimonials, metrics and photography — so any pattern that needs them is unusable here.
- **Desktop is the real usage scene.** Wide screens, long sessions, several tabs of the same product open at once. Narrow widths must not break; no flow is designed for a phone.
- **Four roles, one information architecture.** No role-scoped navigation, dashboards or menus. Everything must read to a business owner with no SAFe training *and* to a solution architect scanning dependencies.
- **Long generated prose is the primary content type.** Findings, assumptions, acceptance criteria, risks. This is a reading product wearing a dashboard's frame.
- **Uncertainty is the most valuable output.** "Attention" is the most-used state in the system, not an exception path. The design must make an unresolved thing the most legible thing on the screen.
- **Generated content is never business truth.** Authorship and approval state have to be visible without a person hunting for a label.
- **Deterministic offline operation is first-class.** No CDN dependency for fonts, icons or anything else.
- **WCAG 2.2 AA is binding**, with five criteria beyond 2.1 AA that this product's surfaces all touch.
- **Stack:** React 19 + Vite + Tailwind 4, CSS custom properties as the token layer, `lucide-react` icons, Tailwind utilities confined to a named layer (ADR-0048), three breakpoints (ADR-0049).

---

## 2. What the generator proposed, and what was taken

The `--design-system` pass returned a generic enterprise-SaaS recommendation. Recorded here so the divergence is a decision, not an oversight.

| Generator | Verdict | Reasoning |
|---|---|---|
| Pattern: **Enterprise Gateway** — hero video, industry tabs, client logo carousel, "Contact Sales" | **Rejected outright** | There is no landing page, no sales surface, and no permission to invent logos or metrics. The pattern has nothing to attach to. |
| Style: **Data-Dense Dashboard** | **Adopted, as the frame** | Sortable tables, sticky headers, always-reachable filters, compact cards, export as a first-class action, maximum information per screen. Correct for the worklist, review and backlog screens. |
| Style: **E-Ink / Paper** (from the `style` search) | **Adopted, as the content register** | Calm high-contrast reading surface, no decoration, no gradients, monochrome discipline. Correct for the prose the product actually produces. |
| Style: **Minimalism & Swiss** (from the `style` search) | **Adopted, as the discipline** | Grid-based, single accent, no shadow on anything in flow, hierarchy carried by type rather than ornament. |
| Style: **Dark Mode (OLED)** — `#000000`, neon accents, glow | **Rejected** | Pure black plus vibrant accents is an entertainment and coding aesthetic, and it causes halation over a long reading session. §4.3 uses an elevated dark-neutral ramp instead. The *contrast targets* from that entry are kept. |
| Colours: primary `#1E40AF` / `#2563EB`, CTA `#F59E0B` amber or `#F97316` orange | **Rejected** | The CTA hue collides head-on with the attention state, which is this product's most-used status. A call to action that looks like an unresolved question is a defect, not a style choice. |
| Typography: **Fira Code** headings + **Fira Sans** body | **Rejected** | A monospace heading face is a developer-tool signal, and one of the four users has no technical training. Mono is kept, scoped to machine strings (§5). |
| Typography: **Lexend + Source Sans 3** ("Corporate Trust", accessibility-led) | **Considered, partly adopted** | The accessibility-first reasoning is adopted; the specific pairing is not, because it has no answer for the long-form reading register. |
| Typography: **Newsreader + Roboto** ("News Editorial", long-form-led) | **Adopted as reasoning** | A reading face for document prose and a neutral grotesque for chrome is the right two-register model. Different families chosen in §5. |
| Effects: hover tooltips, row highlighting, smooth filter animation, chart zoom | **Adopted** | |
| Effects: **data loading spinners** | **Rejected** | One loading idiom — skeletons that reserve layout space (§9). The only spinner in the system is for a running AI job, where indeterminate duration is the honest signal. |
| Anti-patterns: ornate design, no filtering | **Adopted** (§14) | |
| UX rule set: reduced motion, focus states, 4.5:1 contrast, excessive motion, easing functions, motion sensitivity | **Adopted in full** (§9, §13) | This is where the skill contributes most. |
| Pre-delivery checklist | **Adopted and extended** (§16) | Extended to WCAG 2.2 and to dark mode, neither of which the generic checklist covers. |

**Net:** the skill supplies the density frame, the reading register, the UX rule set, the chart guidance and the checklist. Identity — palette, type, shape, motion feel — is decided here, because after the reset there was nothing left to defer to.

---

## 3. Style direction

### Working Paper

> A reading surface with a dashboard's frame. The interface is the desk; the requirement is the paper on it.

The real activity in this product is a person reading a document carefully, annotating what is uncertain, and signing something. It is not monitoring, and it is not data exploration. So the frame is dense and instrumented — tables, filters, sticky headers, counts — while the content it holds is set like a document: generous measure, high contrast, no decoration, nothing moving.

Three commitments define it:

1. **Chrome recedes, content does not.** Navigation, rails and toolbars sit on a quiet paper ground with hairline separation and no shadow. Panels holding a requirement, a finding or a story get the full white surface and the wider type. If you squint, you should see the content, not the furniture.
2. **The only loud thing is the unresolved thing.** One accent, spent once per screen. Attention is the loudest *status*. A screen whose prettiest element is decorative has failed Principle 1.
3. **Nothing pretends to be finished.** Generated content carries its provenance, unapproved content carries its state, stale content says so. The visual system has no "polished" mode that hides these.

**What this direction is not:** not a glass, neumorphic or gradient surface treatment; not an OLED dark aesthetic; not a marketing-grade landing style; not a consumer app. No illustration, no photography, no decorative iconography.

**Density registers.** Three, applied by context, never mixed inside one panel:

| Register | Where | Row height | Padding | Type |
|---|---|---|---|---|
| **Chrome** | Sidebar, header, toolbars, filter bars, breadcrumbs | 32–36px | 8/12px | Interface face, 0.8125rem |
| **Table** | Worklist, activity, revisions, document catalogue, backlog tree | 44px | 12/16px | Interface face, 0.875rem |
| **Document** | Findings, questions, epic/feature/story bodies, acceptance criteria, source text | auto | 20/24px | Document face, 1rem / 1.6 |

The old system's 36px table rows rise to 44px. `ux-plan.md` §3.3 notes that the Breakdown workspace's larger targets were a genuine win; this brings that win into the system rather than converging it away, and it clears WCAG 2.2 target size with room to spare.

---

## 4. Colour

### 4.0 Token architecture

Three layers. Components read **only** layer 3.

```
1. Ramp      --indigo-600, --slate-900, --amber-700 …   raw values, one place, never referenced by a component
2. Theme     --surface, --ink, --accent, --warning …    semantic; redefined under the dark selector
3. Component --button-bg, --table-row-hover …           optional, only where a component needs its own knob
```

Themes switch on `:root[data-theme="dark"]` **and** `@media (prefers-color-scheme: dark)`, guarded so an explicit light choice wins:

```css
:root { /* light theme values */ }
:root[data-theme="dark"] { /* dark theme values */ }
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) { /* dark theme values */ }
}
```

`color-scheme: light dark` is declared on `:root` so form controls, scrollbars and the native focus fallback follow. Theme choice persists per user; system preference is the default.

**No component may reference a hex.** `ux-plan.md` §3.9 counts 365 hardcoded hex values across 40+ distinct colours outside `tokens.css` — the single largest tax on the redesign. Phase 0 tokenises or deletes every one.

### 4.1 The accent — Signal Indigo

`#4338CA`. Chosen by elimination rather than taste: green, amber and red are permanently spent on approved, attention and blocking, and blue is the natural "reference / system name" register. Indigo is the one remaining hue that is unmistakably not a status, reads as authoritative rather than playful, and survives inversion into a dark theme without turning neon.

It means exactly one thing: **act here**. The next action, the current step, the thing waiting on a person.

### 4.2 Light theme — Paper

| Token | Value | Role |
|---|---|---|
| `--canvas` | `#F6F6F3` | Page ground. Warm neutral paper — never pure white, never blue-tinted. |
| `--surface` | `#FFFFFF` | Panels, cards, table bodies, dialogs. |
| `--surface-sunken` | `#ECECE7` | The one recessed tone: rails, insets, skeletons, table headers. |
| `--surface-raised` | `#FFFFFF` | Popovers, menus, toasts — separated by shadow, not tone (§8). |
| `--ink` | `#14171A` | Headings, body, anything that must be read first. |
| `--ink-soft` | `#3A4047` | Secondary prose, table cells. |
| `--ink-muted` | `#5B646D` | Metadata, timestamps, counts, helper text. |
| `--ink-faint` | `#656D76` | The floor. Recessed but still legible; nothing lighter may carry text. |
| `--line` | `#DCDCD5` | Decorative hairline **inside** a bounded surface. Never the sole identifier of a control. |
| `--line-strong` | `#85857E` | Control boundary — inputs, secondary buttons, checkboxes, structural table borders. |
| `--accent` | `#4338CA` | The one brand colour. |
| `--accent-strong` | `#352BA3` | Hover and active on accent. |
| `--accent-wash` | `#EDEBFB` | Accent ground: the current step, and the item being viewed. Not provenance — see §4.5. |
| `--on-accent` | `#FFFFFF` | Text and icons on a filled accent surface. |
| `--success` | `#136B45` | Approved, resolved, passing. |
| `--success-wash` | `#E3F1E9` | |
| `--warning` | `#8A4B08` | **Attention** — unresolved, stale, uncertain, assumed. The most-used state. |
| `--warning-wash` | `#FAEFDF` | |
| `--warning-edge` | `#B96B12` | Non-text only: left edges, borders, chart strokes. Never carries a glyph. |
| `--danger` | `#B3231D` | Blocking, error, failed, rejected. |
| `--danger-wash` | `#FAE6E4` | |
| `--focus` | `#4338CA` | Focus ring, except on an accent-filled surface (§4.6). |
| `--focus-inverse` | `#FFFFFF` | Focus ring on an accent-filled surface. |

### 4.3 Dark theme — Slate

Not an inversion of the light theme, and not OLED black. Pure black under a light accent produces halation that makes long prose painful, so the ramp starts at an elevated near-black and lightness carries elevation (§8).

| Token | Value | Role |
|---|---|---|
| `--canvas` | `#111316` | Page ground. |
| `--surface` | `#191C20` | Panels, cards, table bodies. Lighter than canvas — elevation goes up, not down. |
| `--surface-sunken` | `#0C0E11` | Rails, insets, skeletons, table headers. |
| `--surface-raised` | `#22262B` | Popovers, menus, dialogs, drawers, toasts. |
| `--ink` | `#E9EBED` | Never `#FFFFFF`. Pure white on dark is the halation source. |
| `--ink-soft` | `#C2C8CE` | |
| `--ink-muted` | `#9AA2AA` | |
| `--ink-faint` | `#8B939B` | The floor. |
| `--line` | `#2B3036` | Decorative hairline. |
| `--line-strong` | `#606870` | Control boundary. |
| `--accent` | `#A9A2FF` | Indigo lightened for a dark ground. |
| `--accent-strong` | `#C3BDFF` | Hover and active — **lighter**, not darker. |
| `--accent-wash` | `#211F36` | |
| `--on-accent` | `#15122B` | Text on a filled accent surface is **dark**, not white. |
| `--success` | `#5CCB93` | |
| `--success-wash` | `#10251C` | |
| `--warning` | `#E3A44D` | |
| `--warning-wash` | `#2A1F10` | |
| `--warning-edge` | `#C98A33` | |
| `--danger` | `#FF8E85` | |
| `--danger-wash` | `#2E1614` | |
| `--focus` | `#A9A2FF` | |
| `--focus-inverse` | `#15122B` | |

**Five dark-theme rules that are not optional:**

1. **No pure black ground and no pure white text.** `#111316` and `#E9EBED` are the outer bounds.
2. **Elevation is lightness, not shadow.** A shadow on a dark ground is nearly invisible. Every floating layer moves one step up the surface ramp *and* keeps its 1px `--line` border. Shadow stays only as a secondary cue (§8).
3. **Hover goes lighter.** The light theme darkens on hover; the dark theme lightens. Reusing the light-theme direction produces a hover state that reads as disabled.
4. **A filled accent takes dark text.** `#FFFFFF` on `#A9A2FF` measures **2.26:1** — a fail. `--on-accent` `#15122B` measures **8.06:1**.
5. **Washes lose their power in dark.** Measured: `--accent-wash` against `--surface` is **1.07:1** in dark versus **1.17:1** in light. Neither is enough alone, and dark is worse. Provenance and status therefore never rest on a wash in either theme — see §4.5.

### 4.4 The three colour rules

1. **One accent, once.** `--accent` is spent once per screen, on the next action or the current step. Two accents on a screen means one of them is wrong. There is no secondary brand colour and no separate CTA colour.
2. **Quiet ground, loud state.** Neutrals do all the structural work. Colour appears only where it carries a status, a provenance or the single next action. A panel tinted for decoration is a bug.
3. **Status colour is reserved vocabulary.** Green, amber and red mean approved, attention and blocking — everywhere, including charts (§12). A green bar that means "Q3" is a defect.

`--danger` and `--accent` sit far enough apart in hue to be told apart, and their roles never overlap: accent means *act here*, danger means *this is wrong*.

### 4.5 Status and provenance — never colour alone

Every status carries **at least two channels**: colour plus shape or text. Every provenance carries **at least two**: ground plus a label.

| State | Ground | Ink | Second channel |
|---|---|---|---|
| Approved | `--success-wash` | `--success` | Filled check glyph |
| Attention | `--warning-wash` | `--warning` | 3px `--warning-edge` left edge, plus the count in words |
| Blocking | `--danger-wash` | `--danger` | 3px `--danger` left edge, plus "Blocks confirmation" |
| Neutral / reference | `--surface-sunken` | `--ink-muted` | A register, not a status — system names, catalogued evidence, IDs |

**Provenance.** AI-generated and human-edited content both sit on `--surface-sunken`, and are told apart by **glyph plus label**: a spark and `Generated`, a pen and `Edited`. Neither carries a wash of its own.

*Amended.* This rule previously put AI-generated content on `--accent-wash`. Two things retired it. The measured ground separation was 1.17:1 in light and 1.07:1 in dark, so the wash was never a signal a person could rely on — §4.3 rule 5 says as much. And spending the accent on a provenance state put it in direct conflict with §4.4's "one accent, once": a measured count on one Backlog screen found nine accent sites, of which the `Generated` badge was the only one carrying neither an action nor a current position. Provenance is a register, not an action and not a status. The glyph is the reinforcement; the label is the guarantee.

`--warning-edge` and every wash tone are **non-text**. `--warning-edge` on `--surface` measures 4.06:1 in light: fine for a border, and it must never carry a glyph or a label.

### 4.6 Focus

`3px solid var(--focus)` at `2px` offset, on `:focus-visible` only, set once globally. On any accent-filled surface — the current-step marker, a primary button — the ring switches to `var(--focus-inverse)`.

Measured: `--accent` against `--surface` is **7.90:1** light and **7.57:1** dark; the inverse ring against the accent fill is **7.90:1** and **8.06:1**. All clear the 3:1 non-text requirement with margin. An accent ring on an accent fill would measure about 1:1, which is why the inversion is a rule rather than a refinement.

`outline: none` without a replacement is prohibited. Unqualified `:focus` is prohibited — a ring on mouse click is noise.

### 4.7 Measured contrast

Computed from the values above. Body text needs 4.5:1, large text (≥24px, or ≥19px bold) 3:1, non-text boundaries and focus indicators 3:1.

**Light — text on `surface` / `canvas` / `sunken`**

| Token | surface | canvas | sunken |
|---|---|---|---|
| `--ink` | 17.99 | 16.62 | 15.18 |
| `--ink-soft` | 10.48 | 9.68 | 8.84 |
| `--ink-muted` | 6.02 | 5.56 | 5.08 |
| `--ink-faint` | 5.25 | 4.85 | 4.43 ⚠ |
| `--accent` | 7.90 | 7.30 | 6.67 |
| `--success` | 6.53 | 6.03 | 5.51 |
| `--warning` | 6.79 | 6.28 | 5.73 |
| `--danger` | 6.61 | 6.11 | 5.58 |

⚠ `--ink-faint` on `--surface-sunken` is 4.43:1. **Not permitted** — on a sunken ground, step up to `--ink-muted` (5.08:1). This is the system's only forbidden pair, and it exists because `--ink-faint` is already the floor.

**Dark — text on `surface` / `canvas` / `sunken` / `raised`**

| Token | surface | canvas | sunken | raised |
|---|---|---|---|---|
| `--ink` | 14.31 | 15.57 | 16.17 | 12.73 |
| `--ink-soft` | 10.13 | 11.03 | 11.46 | 9.02 |
| `--ink-muted` | 6.61 | 7.20 | 7.48 | 5.89 |
| `--ink-faint` | 5.49 | 5.98 | 6.21 | 4.89 |
| `--accent` | 7.57 | 8.24 | 8.56 | 6.74 |
| `--success` | 8.48 | 9.23 | 9.59 | 7.55 |
| `--warning` | 7.88 | 8.58 | 8.91 | 7.02 |
| `--danger` | 7.70 | 8.38 | 8.71 | 6.85 |

**Non-text boundaries (need 3:1)**

| Pair | Light | Dark |
|---|---|---|
| `--line-strong` / `--surface` | 3.71 | 3.02 |
| `--line-strong` / `--canvas` | 3.43 | 3.29 |
| `--line-strong` / `--surface-sunken` | 3.13 | 3.42 |
| `--accent` / `--surface` | 7.90 | 7.57 |
| `--warning-edge` / `--surface` | 4.06 | 5.83 |

This fixes the verified failure in `ux-plan.md` §3.11: the old `--line` `#d4dbe2` measured **1.40:1** on white while doing duty as an input boundary. The split is the fix — `--line` stays decorative (1.38:1 light, 1.29:1 dark, by design) and `--line-strong` is mandatory wherever a border is the only thing identifying a control.

**Status ink on its own wash (need 4.5:1)**

| Pair | Light | Dark |
|---|---|---|
| `--success` / `--success-wash` | 5.60 | 7.99 |
| `--warning` / `--warning-wash` | 5.98 | 7.44 |
| `--danger` / `--danger-wash` | 5.51 | 7.62 |
| `--accent` / `--accent-wash` | 6.73 | 7.33 |

---

## 5. Typography

Two reading registers and one machine register. **All three self-hosted** — `PRODUCT.md` makes deterministic offline operation a first-class mode, so a Google Fonts CDN link is not permissible. `font-synthesis: none`; ship the real weights.

| Family | Role | Weights |
|---|---|---|
| **Public Sans** | Interface. Every control, label, table, nav item, button, badge, heading. | 400, 500, 600, 700 |
| **Source Serif 4** | Document. Requirement text, findings, questions, generated narrative, acceptance-criteria prose, source-document excerpts. | 400, 600, 400 italic |
| **IBM Plex Mono** | Machine strings only. Requirement IDs, checksums, revision fingerprints, JSON export preview, diff bodies. | 400, 500 |

**Why two reading faces.** The skill's `typography` search offered "Corporate Trust" (Lexend + Source Sans 3, accessibility-led) and "News Editorial" (Newsreader + Roboto, long-form-led). This product needs both jobs done: a neutral, unremarkable grotesque for a dense instrument, and a face built for reading paragraphs of careful prose. Public Sans is drawn for the first — it is the US Web Design System's interface face, deliberately characterless and heavily tested for legibility. Source Serif 4 is drawn for the second. The register split also means a person can tell peripherally whether they are looking at the product or at the requirement.

**The register split is not the provenance signal.** Serif means "this is document content", whoever wrote it. Provenance is glyph plus label (§4.5). Conflating the two would make human edits inside a generated story invisible.

**If the serif does not survive review**, the fallback is Public Sans at the Document sizes and line-heights below. The register separation weakens; nothing else changes.

### Type scale

| Role | Family | Size | Weight | Line-height | Tracking | Use |
|---|---|---|---|---|---|---|
| Display | Public Sans | 1.75rem / 28px | 700 | 1.2 | -0.01em | Page `h1` — **the requirement's own title**, one per page (`ux-plan.md` §3.4) |
| Headline | Public Sans | 1.25rem / 20px | 600 | 1.3 | normal | Section and panel heading |
| Title | Public Sans | 1rem / 16px | 600 | 1.4 | normal | Card heading — an Epic, a Feature, a finding group |
| Body | Public Sans | 0.875rem / 14px | 400 | 1.5 | normal | Interface prose, table cells, helper text |
| **Document** | Source Serif 4 | 1rem / 16px | 400 | **1.6** | normal | All requirement and generated prose |
| Document lead | Source Serif 4 | 1.125rem / 18px | 400 | 1.55 | normal | The business need, as first written |
| Label | Public Sans | 0.75rem / 12px | 600 | 1.3 | 0.04em | Field labels, column headers, eyebrows — **sentence case** |
| Meta | Public Sans | 0.8125rem / 13px | 400 | 1.45 | normal | Timestamps, owners, counts |
| Mono | IBM Plex Mono | 0.8125rem / 13px | 400 | 1.5 | normal | IDs, checksums, fingerprints |

### Rules

- **Sentence-case labels.** The previous system set every label in tracked uppercase. That is reversed: all-caps is slower to read, hostile to long labels, and reads as institutional in a product whose voice commitment is plain business language. Uppercase survives in exactly one place — the `NEXT` marker on the next-action affordance (§11), where it is a symbol rather than a word.
- **Weight and size carry hierarchy, not colour.** A heading is not a heading because it is accent-coloured.
- **Measure.** Document prose is capped at **68 characters** (`max-width: 68ch`); interface prose at 80. A requirement body running the full width of a 1440px screen is unreadable however much room there is.
- **14px is the interface floor; 16px is the document floor.** Nothing below 12px renders anywhere, including badges.
- **Numerals.** `font-variant-numeric: tabular-nums` on every table column, count, metric and timestamp. Proportional numerals in a sortable column make scanning harder.
- **No third weight axis.** Four weights in Public Sans, two in Source Serif 4. Light weights are prohibited — they fail contrast at small sizes even when the colour passes.

---

## 6. Spacing and sizing

**4px base grid.** One ladder, no values between steps.

| Token | px | Typical use |
|---|---|---|
| `--space-1` | 4 | Icon-to-label, chip padding |
| `--space-2` | 8 | Control inner padding, tight stacks |
| `--space-3` | 12 | Chrome padding, table cell padding |
| `--space-4` | 16 | Card padding, standard stack gap |
| `--space-5` | 20 | Document block padding |
| `--space-6` | 24 | Panel padding, section gap |
| `--space-8` | 32 | Column gap, major section gap |
| `--space-10` | 40 | Page side padding |
| `--space-12` | 48 | Page top padding |
| `--space-16` | 64 | Clearing fixed chrome |

A value off this ladder is a defect. `--space-16` and above exist only to clear fixed chrome.

**Control sizing.** These are floors, not targets:

| Control | Height | Minimum target |
|---|---|---|
| Primary / secondary button | 36px | 36 × 36 |
| Compact button, chrome control | 32px | 32 × 32 |
| Icon button | 32px | 32 × 32 |
| **Inline text button** | — | **24 × 24** |
| Input, select | 36px | 36 × 36 |
| Table row | 44px | 44 × 44 |
| Checkbox / radio hit area | — | 24 × 24 |

The 24×24 floor is WCAG 2.2 **2.5.8**, and it is the redesign's fix for the verified failure in `ux-plan.md` §3.11: `.text-button` is used standalone for Cancel, Retry, Mark read, Clear all and Enable browser alerts at 0.72–0.75rem, well under the minimum. The primitive enforces it — `min-height: 24px; min-width: 24px; display: inline-flex; align-items: center` — so no screen has to remember. Targets sitting closer than 24px to each other get spacing, not just size.

---

## 7. Radius

Deliberately softer than the retired 2/4/8 ladder, which read as institutional. Five steps, nothing between them.

| Token | Value | Applies to |
|---|---|---|
| `--radius-xs` | 3px | Status marks, chart marks, selection outlines |
| `--radius-sm` | 6px | Buttons, inputs, selects, chips, badges, table-row hover |
| `--radius-md` | 10px | Cards, panels, rails, disclosures, empty states |
| `--radius-lg` | 16px | Dialogs, drawers, popovers, toasts |
| `--radius-full` | 999px | Filter pills, avatars, step numbers, counts |

**Nesting rule.** An inner radius is the outer radius minus its padding, floored at `--radius-sm`. A 6px control inside a 10px panel with 16px padding stays 6px — do not match the parent.

---

## 8. Elevation

**Anything in the document flow is flat.** A 1px hairline plus a half-step of surface tone does all the separating. Shadow is reserved for layers that genuinely float above the page, and it is a *cue*, never the only one — every elevated layer also carries a border.

| Token | Light | Dark | Layer |
|---|---|---|---|
| `--elev-0` | `none` | `none` | Everything in flow: panels, cards, tables, rails, the header |
| `--elev-1` | `0 1px 2px rgb(20 23 26 / 0.06), 0 2px 8px rgb(20 23 26 / 0.06)` | `0 1px 2px rgb(0 0 0 / 0.40)` + `--surface-raised` ground | Hover lift on an interactive row or card |
| `--elev-2` | `0 4px 12px rgb(20 23 26 / 0.10)` | `0 4px 12px rgb(0 0 0 / 0.50)` + `--surface-raised` | Dropdowns, menus, popovers, tooltips |
| `--elev-3` | `0 12px 28px rgb(20 23 26 / 0.14)` | `0 12px 28px rgb(0 0 0 / 0.55)` + `--surface-raised` | Drawers — Source, People |
| `--elev-4` | `0 20px 48px rgb(20 23 26 / 0.18)` | `0 20px 48px rgb(0 0 0 / 0.60)` + `--surface-raised` | Modals, toast stack |

**Rules.**

- **Never a shadow on a button.** Buttons answer hover with colour. A lifting button shifts layout and breaks the no-layout-shift rule.
- **Never a shadow on the header, the sidebar or a rail.** Fixed chrome separates with `--line`.
- **In dark, the tone step *is* the elevation.** Shadows are kept for continuity but carry almost nothing; a layer that only darkens the ground behind it is invisible. Every dark elevated layer moves to `--surface-raised` and keeps a 1px `--line` border.
- **The accent edge is the one emphasis device.** A 3px left border carrying `--accent` for the current or next thing, or a status colour for a flagged one. Do not invent a second — no glows, no heavy outlines, no colour-filled panels.
- Scrim behind a modal or drawer: `rgb(20 23 26 / 0.45)` light, `rgb(0 0 0 / 0.65)` dark.

---

## 9. Motion

Motion here exists to explain a change of state, never to decorate. The skill flags reduced motion, excessive motion and easing as its highest-severity animation items; all three are adopted.

### Tokens

| Token | Value | Use |
|---|---|---|
| `--motion-fast` | 120ms | Hover, focus, colour and border changes |
| `--motion-base` | 180ms | The default: disclosure, chip toggle, tab change |
| `--motion-slow` | 240ms | Popovers, dropdowns, toast entry |
| `--motion-slower` | 320ms | Drawers and modals — the largest travel earns the longest duration |
| `--ease-out` | `cubic-bezier(0.2, 0, 0, 1)` | Entering, expanding, appearing |
| `--ease-in` | `cubic-bezier(0.4, 0, 1, 1)` | Exiting, collapsing, dismissing |
| `--ease-move` | `cubic-bezier(0.4, 0, 0.2, 1)` | Moving between two on-screen positions |

### Rules

- **120–320ms.** Nothing over 500ms; nothing instant on hover. Linear easing is prohibited for UI — it reads mechanical.
- **`transform` and `opacity` only.** Never `width`, `height`, `top`, `left` or `margin`. Layout-animating properties cause jank on a 1440px table.
- **Two animated elements per view, maximum.** The skill rates excessive motion high-severity, and on a screen of thirteen stacked sections it is also a comprehension problem.
- **Data does not animate in.** Findings, table rows, backlog items and questions appear at full opacity. An entrance animation on the list a person is trying to read delays the reading for no gain.
- **Nothing decorative animates, ever.** Infinite animation belongs to loading indicators alone.
- **Hover never moves anything.** Colour, border and background respond; position and size do not.
- **State changes leave a mark.** If a transition communicates something — an answer resolved, an item gone stale — a persistent visual marker must remain once it ends, or a reduced-motion user learns nothing.

### Loading — one idiom

**Skeletons.** Hairline-gapped bars on `--surface-sunken`, pulsing opacity 0.55 → 1 over 1.4s, in page / panel / row / inline shapes, announced through `role="status"` with the shimmer `aria-hidden`. Skeletons reserve layout space, which is also how the system satisfies the no-content-jumping rule.

The generator's "data loading spinners" is rejected with **one exception**: a running AI job, where duration is genuinely unknown and a skeleton would imply progress the system cannot see. That spinner is the small accent ring in the job panel, and it is the only one in the system.

### Reduced motion

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
```

Plus, specifically: the skeleton pulse becomes a static `--surface-sunken` fill; drawers and modals appear without travel; auto-scroll on navigation becomes an instant jump. Tailwind utilities pair with `motion-reduce:transition-none` and `motion-reduce:animate-none`.

---

## 10. Layout, breakpoints, z-index

### 10.1 Frame

Per `ux-plan.md` §4 — **one shell on every route, including Backlog.**

| Element | Size | Notes |
|---|---|---|
| Header | 56px fixed | Brand, global search, notifications, account, primary action. **No navigation row** (supersedes ADR-0050). |
| Sidebar | 240px, collapsible to 56px | The only global navigation. Four destinations. Present on every route. |
| Stage rail | 240px | Inside the requirement frame only. Six steps (`ux-plan.md` §4), vertical, persistent. |
| Main column | max 1360px | 40px side padding; 24px at `md` and below. |
| Document column | max 68ch | Inside main, for prose. |

The header drops from 64px to 56px and the sidebar from 254px to 240px: with the stage rail promoted to a persistent vertical element, the old horizontal stepper's height is reclaimed.

Multi-column work is proportional, not fixed — the clarify workspace is `minmax(280px, 0.72fr)` source rail against `minmax(0, 2fr)` questions at a 32px gap.

### 10.2 Breakpoints — three, and only three

ADR-0049 survives the identity reset. Declared once in the Tailwind theme and read by stylesheets through `theme()`, so CSS and components cannot drift.

| Token | Width | Fold |
|---|---|---|
| `sm` | 640px | Headings stack; cards go full width; the stage rail scrolls horizontally |
| `md` | 900px | Sidebar collapses to icons; two-column grids become one; drawers replace side panels |
| `lg` | 1050px | The widest multi-pane layouts fold — the source rail drops beneath the questions |

A media query at a fourth width is a defect, not a refinement. The skill's 375 / 768 / 1024 / 1440 checkpoints are a **testing matrix**, not breakpoints: verify at those widths, fold only at the three above.

### 10.3 Z-index

`ux-plan.md` §3.9 records nine distinct values across the stylesheets, including a bare `100`. One named scale, nothing outside it, nothing above 50.

| Tier | Value | Layer |
|---|---|---|
| Base | `1` | In-flow lifts, sticky rails |
| Sticky | `10` | Sticky table headers, stage rail |
| Chrome | `20` | Fixed header, sidebar |
| Overlay | `40` | Modal scrim and dialog, drawers |
| Top | `50` | Toast stack, notification popover, skip link |

A positioned ancestor with its own z-index creates a new stacking context and isolates its children — that, not the number, is usually the real cause of "z-index isn't working".

### 10.4 Focus must not be obscured — WCAG 2.2 2.4.11

The fixed header and any sticky rail can cover a focused element during keyboard traversal. Every scroll container sitting under fixed chrome declares `scroll-padding-top` equal to the header height plus 8px, and sticky panels declare `scroll-margin`. `ux-plan.md` §3.11 flags this as unverified; it is a **must-test** on every route before a phase is called done — tab from the skip link to the last control at 1440px and at 900px.

---

## 11. Components

Sturdy and legible before elegant. Each primitive is built to 2.2 AA at the primitive, so no screen has to remember (`ux-plan.md` §5, Phase 0).

**Button.** `--radius-sm`, 36px minimum height, 8/16px padding, Label type in **sentence case**, written as the act ("Save and analyse business need") rather than the object. Primary: `--accent` ground, `--on-accent` text. Secondary: transparent, `--line-strong` border, `--ink` text. Ghost: no border until hover. Danger: `--danger` ground, reserved for destructive confirmation. Hover changes ground colour only — no lift, no shadow, no scale. Disabled: `--ink-faint` on `--surface-sunken`, `cursor: not-allowed`, and **a gated primary action stays visible and explains why** rather than disappearing. Async actions disable for the duration and say what is running.

**Inline text button.** Underlined, `--accent`, 24×24 minimum (§6). Used for Cancel, Retry, Mark read, Clear all.

**Input / select / textarea.** `--surface` ground, 1px `--line-strong`, `--radius-sm`, 36px height. A real `<label for>` above, at Label type — never a placeholder standing in for a label. Placeholders are worked examples ("Example: High-speed business bundles"). Focus: border to `--accent` plus the global focus ring. `aria-invalid` turns the border `--danger` with a bold message **below the field, beside the problem**, linked by `aria-describedby`.

**Card / panel.** `--radius-md`, `--surface` (or `--surface-sunken` when inset), 1px `--line`, `--elev-0`, 24px padding. Status variants add the 3px left edge plus the matching wash.

**Table.** Sticky header on `--surface-sunken`, 44px rows, `--line` dividers, row hover as a tone shift with `cursor: pointer` where the row is clickable. **Column headers are sortable buttons** exposing `aria-sort` — `ux-plan.md` §3.12 records that only a sort dropdown exists today. Multi-select through a leading checkbox column, with a bulk-action bar that replaces the filter bar in place rather than floating over content. Filters stay visible; *no filtering* is a named anti-pattern.

**Badge / chip / pill.** Badge: `--radius-sm`, no border, 12px/600 on a status wash, always with its second channel (§4.5). Filter pill: `--radius-full`, `--surface` with `--line-strong`, filled with `--accent` and `--on-accent` when active. Only statuses with a non-zero count render.

**Sidebar.** 240px, `--surface-sunken`, `--line` right edge, four destinations, collapsible to 56px icons with `aria-expanded` and persisted state. Active item: `--accent-wash` ground plus a 3px `--accent` left edge. This one component replaces all three of the navigation systems in `ux-plan.md` §3.1.

**Stage rail (signature).** Six vertical steps — Source, Clarify, Knowledge, Confirm, Backlog, Review & approve. Complete: `--success` check plus the step name in `--ink`. Current: `--accent-wash` ground, 3px `--accent` left edge, `--accent` label. Blocked: `--ink-faint` with a hollow ring — **navigable, because the destination explains itself better than a disabled control can**, but never reading as available. Every state carries a glyph as well as a colour.

**Next action (signature).** One per workspace. A bordered block with a 3px `--accent` left edge, a small uppercase `NEXT` marker, and the action in the person's own words — "Answer 4 blocking questions". The only element in the product allowed to tell somebody what to do.

**Empty state.** One row: a soft-tinted rounded icon tile, a Title-size heading, and one `--ink-muted` line explaining what would be here and how to start. Dashed 1px `--line`, `--radius-md`. Never a large illustration, never a centred hero.

**Toast.** Bottom-left stack, four visible maximum. `--surface-raised`, 1px `--line`, `--radius-lg`, `--elev-4`, and a 3px left edge whose colour carries the tone — matched by the icon and nowhere else. Never the only place an error is reported.

**Modal / drawer.** One primitive, per ADR-0047's surviving intent. Traps focus, closes on Escape, returns focus to its trigger, labelled by its heading through `aria-labelledby`. Drawers are `--elev-3`; modals `--elev-4`.

**Help (WCAG 2.2 3.2.6).** A single help affordance in the same header position on every route. `ux-plan.md` §3.11 records that none exists — intake guidance hides in a `<details>` and nothing equivalent exists elsewhere. One affordance, one position, every page.

**Icons.** `lucide-react`, 24×24 viewBox, `aria-hidden="true"` when decorative, `aria-label` or `sr-only` text when an icon is the whole control. **Never an emoji as an icon.**

**Enum labels.** One label map in the presentation layer for every enum the API returns. `.replaceAll("_", " ")` never reaches a user — `ux-plan.md` §3.7 finds it in at least six places, rendering literal strings such as `all`, `blocking` and `under review`.

---

## 12. Data and charts

There is no chart library in the frontend today — `/reports` renders three tables and a `lucide-react` icon. This is a specification for `ux-plan.md` Phase 8, not a description of what exists.

**Library:** Recharts — it composes as React components and keeps SVG in the DOM where it can be labelled.

| Question | Chart | Notes |
|---|---|---|
| Weekly throughput over 4 / 12 / 26 weeks | Line; area only for a single series | 20% fill opacity if filled |
| Requirements by workflow state | Horizontal bar, sorted descending | Not a pie — the categories are ordinal stages |
| Source → Clarify → Knowledge → Confirm → Backlog → Review drop-off | Funnel | Label every stage with an absolute count **and** a percentage |
| Clarification resolution rate | Line, with the target as a reference line | |
| Oldest blockers | Horizontal bar, sorted by age | The bar is the age; the label is the requirement |
| Approval turnaround | Line, or scatter when per-requirement outliers are the point | |

**As built in Phase 8.** Weekly throughput shipped as five small-multiple column charts — one per measure, inline SVG, no library — rather than one line chart. The measures differ by an order of magnitude, so a shared axis flattened the small ones; each multiple prints its own 0 and maximum, and the page says the scales differ. Bars are ink, not a categorical ramp: each multiple is one series, named by its heading. The week still in progress is drawn outlined, not in a different shade. The weekly table sits under the charts in a disclosure, with every count linked to its activity. Oldest blockers shipped as a table sorted by age rather than bars.

**Chart colour.** Series that *are* statuses use the §4.5 palette exactly. Series that are not draw from a categorical ramp that excludes green, amber, red and `--accent` entirely — otherwise a bar meaning "Q3" reads as "approved". Never encode by colour alone: pattern, direct label or shape carries it too. Both themes need the ramp defined; a light-theme series palette on a dark ground loses its two lightest steps.

**Accessibility.** Every chart ships a table alternative — the underlying rows in a `<table>`, visible or in a disclosure. Axis labels and units always present. Hover tooltips supplement the data, never replace it.

---

## 13. Accessibility — WCAG 2.2 AA

Settled and binding (`PRODUCT.md`, `ux-plan.md` §0). This supersedes the WCAG 2.1 AA proposal in the previous version of this document.

### The five criteria beyond 2.1 AA

| Criterion | Requirement here | Where |
|---|---|---|
| **2.5.8 Target size (Minimum)** | 24×24px floor, enforced in the primitive. Fixes the verified `.text-button` failure. | §6 |
| **2.4.11 Focus not obscured (Minimum)** | `scroll-padding-top` under fixed chrome; tab-traversal test per route before a phase is done. | §10.4 |
| **3.2.6 Consistent help** | One help affordance, same header position on every route. | §11 |
| **3.3.7 Redundant entry** | Nothing supplied earlier in the journey is asked for again. Clarify answers carry into Confirm; intake attachments carry into Source. | flow level |
| **2.5.7 Dragging movements** | Every drag has a single-pointer alternative — reorder from a menu, resize with a numeric control. | component level |

### The standing bar

| # | Requirement | Severity |
|---|---|---|
| 1 | Text ≥ 4.5:1; large text ≥ 3:1; verified in **both** themes | High |
| 2 | Non-text boundaries and focus indicators ≥ 3:1 | High |
| 3 | Visible `:focus-visible` on every interactive element; never `outline: none` without a replacement | High |
| 4 | All functionality keyboard-reachable, tab order matching visual order, no traps | High |
| 5 | Skip link first in tab order on every route — fixed chrome precedes content everywhere | High |
| 6 | Every input has a `<label for>`; errors beside the field, linked by `aria-describedby` | High |
| 7 | Icon-only controls carry `aria-label` or `sr-only` text | High |
| 8 | Status never by colour alone — shape, glyph or text always | High |
| 9 | `prefers-reduced-motion` honoured | High |
| 10 | Modals trap focus, close on Escape, return focus to the trigger | High |
| 11 | Async regions announce through `role="status"`; layout space reserved | Medium |
| 12 | One `<h1>` per page — **the requirement's title** — no skipped levels | Medium |
| 13 | Meaningful images have alt text; decorative ones `aria-hidden` | Medium |
| 14 | `cursor: pointer` on everything clickable | Medium |
| 15 | Semantic landmarks — `header`, `nav`, `main`, `aside`, `footer` — each named where repeated | Medium |

---

## 14. Anti-patterns

### From the generator

- **Ornate design.** No decorative gradients, no illustration, no flourish carrying no information.
- **No filtering.** Any list that can outgrow a screen ships filters and sort.
- **Excessive motion.** More than two animated elements in a view.
- **Linear easing** on UI transitions.
- **Emojis as icons.** Arbitrary z-index. Colour-only status. Hover states that shift layout. Spinners where a skeleton belongs. Uniform padding across breakpoints.

### From this system

- **A second accent.** There is no secondary brand colour and no separate CTA colour. An amber or orange CTA is specifically prohibited — it collides with the attention state.
- **A hardcoded hex in a component.** Tokens only. This is the drift that produced 365 of them.
- **Status colour spent on a non-status**, especially in charts.
- **A shadow on anything in the document flow**, and a shadow on any button, ever.
- **A radius, spacing value or duration off the ladder.**
- **Tracked uppercase labels.** Sentence case, except the `NEXT` marker.
- **A third density register inside one panel.**
- **A fourth breakpoint.**
- **Designing for a phone at the desktop review scene's cost.**
- **Role-based navigation, dashboards or menus** — excluded by decision (`ux-plan.md` §0), not by omission.
- **A fifth title on a stage route.** The `h1` is the requirement's title; the stage is named by the rail (`ux-plan.md` §3.4).
- **Raw enum strings as UI copy.**

### Specific to this product's principles

- **Softening uncertainty.** An unresolved question rendered as a tasteful grey note, a blocking item that looks like a tip, an assumption styled as a fact. `PRODUCT.md` Principle 1: never let a surface bury an open question to look finished.
- **Blurring who acted.** Generated content presented without provenance, or an approval affordance that looks like a generate affordance. Principle 2: generation and approval are different acts by different means.
- **Approval above evidence.** `ux-plan.md` §3.6 documents the review screen rendering approve buttons above the material they approve. Evidence precedes the decision, always.
- **Method vocabulary at the boundary.** INVEST, SPIDR, "artifact status", "analysis_readiness" reaching a business owner. Principle 3.
- **Progress theatre.** A determinate bar for an indeterminate job, a percentage the system cannot actually know, a success animation before the server confirmed.
- **Silent loss.** A regeneration that visually replaces human-edited content without flagging it. Principle 4: flag, never overwrite.

### Dark mode specifically

- Pure black ground (`#000000`) or pure white text (`#FFFFFF`).
- Reusing light-theme shadows and expecting them to read.
- Hover that darkens.
- White text on the filled accent (measured 2.26:1).
- Relying on a wash for provenance (measured 1.07:1 separation).
- Shipping a light-mode-only chart palette.
- Images, logos or screenshots with baked-in white grounds.

---

## 15. Implementation notes

**Token file.** `tokens.css` becomes the only source of colour, type, space, radius, elevation and motion. `ux-plan.md` Phase 0 collapses the 15 stylesheets and resolves the 216 duplicate selectors so import order stops being load-bearing, and deletes the three dead visual generations (`#201e1d` warm near-black, `#ec3013` orange-red, `#81e4d0` teal) outright rather than porting them.

**Tailwind 4.** Utilities stay in their named layer (ADR-0048). Theme values are declared once in the Tailwind theme so `theme()` and the custom properties cannot drift. `focus-visible:` not `focus:`. `motion-reduce:` alongside every transition. Responsive padding scales; one padding for all widths is a smell.

**React 19.** Every async region renders three states — pending (skeleton, control disabled), error (inline, beside the problem), empty (`EmptyState` with a way to start). A component with only a success state is incomplete. Stable keys in lists, never the array index where rows reorder. Controlled inputs. Virtualize long worklists when they hurt, not before.

**Theme switching.** No flash of the wrong theme: resolve the stored preference in a blocking inline script before first paint and set `data-theme` on `<html>`.

**Presentation only.** Per `CLAUDE.md`: layout, markup, styling and interaction change; hooks, services, state, data fetching and API calls do not. If a redesign appears to need a logic change, raise it rather than making it.

---

## 16. Pre-delivery checklist

**Visual**
- [ ] No hardcoded hex — tokens only
- [ ] No emojis as icons; `lucide-react` at consistent sizing
- [ ] One accent per screen
- [ ] Nothing in flow carries a shadow
- [ ] Radius, spacing and duration all on the ladder
- [ ] Labels in sentence case
- [ ] One density register per panel

**Both themes**
- [ ] Rendered and read in light **and** dark
- [ ] Text ≥ 4.5:1 in both; boundaries and focus ≥ 3:1 in both
- [ ] Dark hover lightens; filled accent takes `--on-accent`
- [ ] Borders visible in both; no wash doing load-bearing work
- [ ] No flash of the wrong theme on load

**Interaction**
- [ ] `cursor: pointer` on everything clickable
- [ ] Transitions 120–320ms, `transform`/`opacity` only
- [ ] Hover shifts no layout
- [ ] Async controls disable and say what is running
- [ ] Errors render beside the problem, not only in a toast

**Accessibility (WCAG 2.2 AA)**
- [ ] Every target ≥ 24×24, including inline text buttons
- [ ] Tabbed end to end at 1440px and 900px — no focused element hidden behind fixed chrome
- [ ] Help affordance present, in the same position
- [ ] Nothing asked twice across the journey
- [ ] Every drag has a single-pointer alternative
- [ ] Skip link first; inputs labelled; icon buttons named
- [ ] Status carries shape or text, not colour alone
- [ ] `prefers-reduced-motion` honoured
- [ ] One `<h1>`, the requirement's title

**Layout**
- [ ] Nothing hidden behind the 56px header or the 240px sidebar
- [ ] Verified at 375 / 768 / 1024 / 1440
- [ ] Folds only at `sm` / `md` / `lg`
- [ ] No horizontal scroll
- [ ] z-index drawn from §10.3
- [ ] Document prose capped at 68ch

**States and meaning**
- [ ] Loading uses `Skeleton`, reserving layout space
- [ ] Empty state present, with a way to start
- [ ] Error state present
- [ ] Provenance visible — generated content labelled, not merely tinted
- [ ] Unresolved and blocking items are the most legible things on the screen
- [ ] No raw enum string reaches a user

**Build**
- [ ] `cd frontend && npm run build` green

---

## 17. Open items

1. ~~**Dark mode is now specified**~~ — *closed.* It shipped in Phase 0 and `ux-plan.md` §6 decision 5 records it.
2. **The serif register needs one review.** Source Serif 4 for document prose is the one genuinely debatable call here. Decide it on a real Clarify screen with real generated findings, not in the abstract. The fallback (§5) is a one-line change.
3. **A categorical chart ramp is not yet specified** — only the constraint that it excludes the four reserved hues. Choose it when Phase 8 starts, in both themes, and add it to §12.
4. ~~**`DESIGN.md` remains stale**~~ — *closed.* It was rewritten from the shipped code at the end of Phase 0 and is the applied summary of this document; this document stays the rationale and measurement record.
5. ~~**`frontend/index.html` still carries the retired title**~~ — *closed.* The static title is **Requirement AI** (Phase 0.1).
