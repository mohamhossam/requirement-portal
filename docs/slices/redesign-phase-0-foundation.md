# Redesign Phase 0 — Foundation: what is left

`docs/ux-plan.md` §5 Phase 0, governed by `docs/design-system.md` (Working Paper).
Presentation only (`CLAUDE.md`): no hook, service, state, fetching or API change.
Every step ends with `cd frontend && npm run build`, `npm run lint`,
`npm run test:coverage` and the Playwright smoke green.

## Where Phase 0 stands (measured on `main` at a028b03)

Already done by earlier passes, and not repeated here:

| Phase 0 item | State |
|---|---|
| 1. Identity and tokens | `tokens.css` carries the Working Paper ramps, Paper and Slate themes, focus, elevation, motion; `index.css` bridges them into Tailwind's theme. Fonts self-hosted. No-flash theme script in `index.html`. |
| 3. Shell | `components/shell/` — `AppShell`, `AppTopBar` (56px), `AppSidebar` (240/56px, persisted), `HelpMenu`, skip link, `scroll-padding` for 2.4.11. `StageRail` and `NextAction` in `app/requirement/`. |
| 4. Primitives | `components/ui/` — Button (incl. the 24×24 `text` variant), Field, Input, Select, Checkbox, Badge, Card, Table, Tabs; plus `Modal` (modal and drawer variants), `Toaster`, `Skeleton`, `EmptyState`, `components/states/`. |
| 5. §3.11 gaps | `--line` / `--line-strong` split exists; `--warning-bright` aliased to `--warning-edge` (non-text only). The `text` Button variant fixes 2.5.8 — **but 7 files still use the legacy `.text-button` class.** |

What remains:

| Measure | Count |
|---|---|
| Hardcoded hex outside `tokens.css` | 193 in 13 stylesheets, 8 in 4 `.tsx` files |
| Dead generations still live | `#201e1d` ×28, `#ec3013` ×14, `#81e4d0` ×3 (plus `#7be0cc` teal) |
| Selectors declared in more than one file | 89 (was 216) |
| Legacy stylesheets | 13 numbered files; import order still load-bearing |
| Deprecated token aliases (`tokens.css` foot) | 15 names, still referenced |
| Legacy `.button` class in markup | 24 files, 94 call sites |
| Legacy `.text-button` class in markup | 7 files, 17 call sites |
| Login page | Navy→teal gradient, teal kicker, 0.82rem radii — the fourth generation (§3.10) |
| `index.html` title | Still "SMB Requirement Review" (design-system §17.5) |

## Steps

Each step is one commit, and each is independently shippable.

### 0.1 Login page and product title — done

`auth/LoginPage.tsx` rebuilt on tokens and primitives (`Button`, `Select`/`Field`,
`ErrorNotice`-style alert): Paper canvas, one bordered surface, Signal Indigo as
the only accent, sentence-case labels, no gradient, no glow, no transform
transitions. Same auth calls, same branches (fake / choices / retry), same copy;
the two eyebrows went (the kicker now sits under the brand name as its
subtitle). The Microsoft mark's fixed brand colours are named in `tokens.css` as
third-party marks, so the page carries no hex. Below `md` only the journey rail
folds away; the smoke test asserts that by role instead of by class. `login-*` rules deleted from `01-foundation.css`
and `02-breakdown-workspace.css`. `index.html` title → "Requirement AI".

### 0.2 Inline text buttons (WCAG 2.2 2.5.8) — done

The 17 `.text-button` call sites move to `<Button variant="text">`, so the 24×24
floor comes from the primitive. `.text-button` and `.danger-text` rules deleted;
a destructive inline action uses the new `text-danger` variant. Measured in the
browser: "Enable browser alerts" renders 25px tall, accent, underlined.

### 0.3 Form controls and the legacy `.button` — done

The element rules for `input`, `select`, `textarea`, `label` are declared in four
files. One declaration in `base.css`: `--surface`, 1px `--line-strong`,
`--radius-sm`, 36px, accent border on focus plus the global ring, `aria-invalid`
→ `--danger`. The 92 legacy `.button` call sites (23 files; login had the other 2) move to `<Button>` / `<ButtonLink>`
and the three `.button` generations are deleted.

As built: the recipe moved to `components/ui/buttonClass.ts`, and `buttonClass()`
dresses the three controls that cannot be a `<button>` or a `<Link>` (two
file-picker labels and a blob-URL anchor) plus Capture's gated "Continue to
analysis", whose disabled look now keys off `aria-disabled`. Two semantics were
kept exactly rather than cleaned up: the 23 Library buttons that were implicit
form submits carry `type="submit"`, and a bare `button` class there — paired
against `button-secondary` — maps to `primary`. The contextual `.button` rules
became `> :is(button, a)` child rules, a `size="sm"` and a `whitespace-nowrap`
at their call sites. The form-control rule no longer touches checkboxes,
radios or file inputs. After this step: 155 hex outside `tokens.css`, 68
cross-file duplicate selectors, no legacy `.button` in markup.

### 0.4 Hex out of the stylesheets — done

File by file, largest first — `04-modernist` (52), `01-foundation` (49),
`06-source-documents` (43), `05-intake-stages` (15), then the rest, then the four
`.tsx` files. Each hex becomes a semantic token or goes with its dead generation.
Nothing is ported from `#201e1d` / `#ec3013` / teal. Exit: zero hex outside
`tokens.css`, enforced by a vitest guard beside `breakpoints.test.ts`.

As built: 193 colour declarations were inventoried (hex, `rgb()`, and the bare
`white`/`black` keywords, which break the dark theme the same way). 44 never
rendered — a later file redeclared the same selector and property — and were
deleted; so were the rules on selectors no markup references (the old dashboard
hero, journey preview, intake guide and loader, all of the teal generation).
The remaining 123 map to semantic tokens: 2px near-black rules became 1px
`--line` hairlines, status frames became the 3px left edge plus the matching
wash, staleness moved from red to `--warning` (§4.5), the reference blue became
the neutral register, the inverted navy reports summary became a sunken inset,
and the one in-flow hover shadow was deleted (§8). The Microsoft mark's colours
are the only theme-independent values, named in `tokens.css`. Guard:
`styles/palette.test.ts` fails on any colour literal outside `tokens.css`, in
CSS or in a component's Tailwind arbitrary value; comments and `mask-image`
alpha stops are exempt.

### 0.5 Collapse the stylesheets — done

With the overrides gone, `04-modernist` and `08-stitch-foundation` (whole files of
overrides of `01`) fold into the rules they override and are deleted. Remaining
rules regroup by surface; the 89 cross-file duplicates reach zero, enforced by a
guard; the "import order is load-bearing" warning is removed because it is no
longer true. Selectors with no markup reference are deleted (dynamic class names
such as `status-${…}` checked by hand first). The deprecated alias block in
`tokens.css` reaches zero and is deleted.

As built: every (media context, selector) is now declared in exactly one
stylesheet. A fold merged each selector's declarations in import order — an
overridden property re-inserted at the end, a later shorthand dropping the
longhands it resets, an earlier `!important` kept — and gave it one home: the
earliest surviving file, except that `12-document-register.css` keeps the three
register selectors it exists to state. `04-modernist.css`, `08-stitch-foundation.css`
(whole files of overrides of 01) and `07-story-quality.css` (a comment) are
deleted; 57 selectors no markup uses went with them, each grep-checked against
the runtime-built `status-`, `kind-`, `save-`, `category-` and `severity-` class
names. The 91 deprecated alias uses were swapped for their targets and the
alias block deleted. File names stay; regrouping by surface can travel with the
screen phases that restyle each surface.

Verified with a local-only computed-style snapshot: 19 routes (worklist, intake,
documents, library, architecture, activity, reports, a clarify-stage and a fully
approved requirement across every stage, login) in both themes, 11,006 elements
and 50 properties each, diffed before and after. Two runs of the unchanged build
set the noise floor (content-sized widths only). After the fold the only
difference was an `ml-auto` margin that follows content width. Dialogs, drawers
and error states are not in that snapshot. Guard: `styles/selectors.test.ts`.

### 0.6 Primitive audit — done

Each §11 primitive checked against its spec and 2.2 AA: a `Panel` (Card inset /
status-edge variants) if Card does not already cover it; Drawer via `Modal
variant="drawer"`; Toast (bottom-left, four max); EmptyState (dashed, one row);
Skeleton (`role="status"`). z-index values drawn only from §10.3.

As built: Button, Field / Input / Select, Checkbox (24px hit area), Badge and
Pill, Card, Table (sticky header, 44px rows, `aria-sort` buttons, in-place bulk
bar), Tabs (roving tabindex, arrows / Home / End), EmptyState, Skeleton and
Toaster already met §11. Card is the Panel — `inset` plus the four status tones
with the 3px edge — so no second primitive was added. Two fixes:

- **Layers.** Six raw values moved onto the §10.3 scale: skip link 100 → `--z-top`,
  notification popover 40 → `--z-top`, the Views popover `z-20` → `--z-top`, intake's
  sticky bar 4 → `--z-sticky`, two bare 1s → `--z-base`. `styles/layers.test.ts`
  fails on any z-index or `z-` utility outside the scale.
- **Drawer.** `Modal` takes `side` and `size` instead of leaving them to caller
  classes, and puts `--radius-lg` on the open edge (§7). Caller classes that set a
  property the primitive already sets win or lose by Tailwind's output order, and
  the navigation drawer had been losing: it asked for 18rem and rendered 30rem —
  the full width of a 375px screen — with 24px padding. It is now 288px, 16px
  padding, radius on the right edge; keyboard open and close return focus to the
  trigger. Found on the way: the People drawer's reviewer controls shrank to a few
  letters a line in the 480px drawer; that row now wraps.

Not in 0.6: about a dozen `.replaceAll("_", " ")` enum strings remain (Knowledge,
Review, Documents, Intake, Capture, Access). Each needs business-language copy,
so they go with the screen phases that own them (2, 3, 5, 6, 7).

### 0.7 Verification and records — done

Build, lint, vitest, smoke. One batched visual pass in both themes at
1440 / 900 / 375, and a keyboard traversal from the skip link on the worklist, a
stage route and the login page. Then: `ux-plan.md` §6 decision 5 (dark mode)
marked closed, and `DESIGN.md` regenerated from the shipped result (§6 decision 4).

As built: the keyboard pass tabbed every stop — not the first 25, as the smoke
test does — on login, the worklist, and a fully approved requirement's clarify,
story and review routes, at 1440px and 900px (up to 50 stops a route). No stop was
hidden under the fixed header or off screen, and the skip link was first wherever
there is chrome. It found four defects, all fixed: the header brand link was 22px
tall (now a 24px minimum); the worklist search drew no focus ring, because its
input suppresses its own outline (the bordered box now carries the ring on
`:has(:focus-visible)`); the "Assigned to me" checkbox's label is now a 24px
target; and Chrome's keyboard-focusable scrollers — the Clarify screen's "What is
settled" column — had no ring, so `base.css` now rings any keyboard-focusable
element outside `tabindex="-1"`. The worklist and saved-view field borders moved
from decorative `--line` to `--line-strong` (§3.11, 1.4.11).

`DESIGN.md` is rewritten from the shipped code as "The Working Paper", with its
`.impeccable/design.json` sidecar; `ux-plan.md` §6 decisions 3–5,
`design-system.md` §17 items 1, 4 and 5, and the stale lines in `PRODUCT.md` are
closed. The local-only snapshot and traversal harness is deleted.

*Count correction.* The 0.2 and 0.3 commit messages say 16 `.text-button` and
44 `.button` call sites. Both undercount: the scripts' own per-file totals were
17, and the 0.3 conversion ran in two batches of which only the second (44) was
tallied. Measured at a028b03 with `git grep -o`, the figures are 17 and 94 (92
converted in 0.3, 2 on the login page in 0.1). The conversions themselves were
complete; `git grep` finds no legacy class left in markup.

## Phase 0 result

| Measure | At a028b03 | Now | Held by |
|---|---|---|---|
| Colour literals outside `tokens.css` | 193 in CSS, 8 in components | 0 | `styles/palette.test.ts` |
| Selectors declared in more than one file | 89 | 0 | `styles/selectors.test.ts` |
| Numbered legacy stylesheets | 13 | 10 (04, 07, 08 deleted) | — |
| Deprecated token aliases | 15 names, 93 uses | 0 | — |
| Legacy `.button` / `.text-button` call sites | 94 / 17 | 0 / 0 | — |
| z-index values off the scale | 6 | 0 | `styles/layers.test.ts` |
| Login page | fourth visual generation | Working Paper | — |
| `DESIGN.md` | retired identity | shipped system | — |

The import order in `index.css` is no longer load-bearing, and the redesign's
screen phases (ux-plan.md §5, Phases 1–9) start from here.

## Not in Phase 0

- Screen redesigns — Phases 1–9.
- `stagePath` behaviour and URL changes — `ux-plan.md` §6 decisions 1–2, product calls.
- Superseding ADRs 0045 / 0047 / 0050 — written with the phase that changes the behaviour they record.
