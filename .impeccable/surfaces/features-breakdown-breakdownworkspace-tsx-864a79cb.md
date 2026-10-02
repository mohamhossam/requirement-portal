---
version: 1
slug: "features-breakdown-breakdownworkspace-tsx-864a79cb"
primary_target: "frontend/src/features/breakdown/BreakdownWorkspace.tsx"
related_targets: ["frontend/src/app/requirement/StageRail.tsx","frontend/src/features/epic/EpicCard.tsx","frontend/src/features/features/FeatureCard.tsx","frontend/src/features/stories/StoryCard.tsx","frontend/src/features/stories/StoryList.tsx"]
---

Scope: the Backlog step of the Requirement workspace — `/requirements/:id/breakdown`, `.../breakdown/epic`, `.../breakdown/features/:featureId`, and `.../breakdown/features/:featureId/stories/:storyId`. Visitor mode: **Operate**.

Audience: Product Owner with business-analyst support, mid-review, multi-session, at a desk on a wide screen. Job: read and shape a generated Epic → Feature → Story backlog, judge provenance and staleness, approve each level. Constraint: presentation only — hooks, services, state, data fetching and API calls are out of bounds (CLAUDE.md). WCAG 2.2 AA is binding.

## Direction contract

THESIS: The backlog is one spine, not a page with a tree bolted to its side. Epic → Feature → Story is depth *inside* the Backlog step, so it unfolds in the same rail that carries the journey — one navigation column, one model. Refuses two category defaults: the three-pane IDE explorer (tree | list | detail) that turns a requirements review into a file browser, and the numbered-gutter card that dresses an unordered backlog as a sequence.

OWN-WORLD: Inherited, not invented — `docs/design-system.md` "Working Paper". Signal Indigo spent once per screen; Paper light and Slate dark both live. Public Sans for interface; Source Serif 4 for everything the AI drafted — story voice, outcomes, acceptance criteria; IBM Plex Mono for identifiers. Flat in flow: 1px `--line` plus a half-step of surface tone, `--elev-1` on hover only. One emphasis device, the 3px accent left edge, already spoken by StageRail — the backlog tree answers in the same words. Radius ladder 6/10/16. No hex reaches a component.

STORY: A Product Owner reopens a requirement mid-review, reads where the journey stands and where they are inside the backlog in one column, reads generated content in a face that says "this is a draft, not the app", judges provenance and staleness without decoding colour, and approves — or regenerates — without an approve button ever preceding the evidence it approves.

FIRST VIEWPORT (desktop, `/breakdown/features/:id`): global sidebar 240px. PageHeader carries the requirement title as `h1`, `id · stage` beneath, Source document / People / History at the right. Below it, two columns. Left, one ~260px spine: six journey steps, and indented beneath step 5 Backlog, the Epic and each Feature with its disclosure and Stories. The item being viewed and the step being viewed share the accent edge and wash. Right: breadcrumb, then the Feature as a flat Card — status badge and MVP/Later badge, name at Title, outcome in serif, splitting rationale and system impact behind disclosures, then the Stories. The primary action sits in the card header, once.

FORM: Single-spine rail with in-place depth. Ranked first of five considered — collapsible third column; drawer at every width; breadcrumb-only; tabbed Epic/Features/Stories. No seed key: this is a surface inside an established, committed world, so no direction roll was run, per new-work §1 "Established world: inherit it" and §3 "a section, component, feature, or state inside an established surface inherits that surface."

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance.

## Unresolved

- Root `DESIGN.md` still records the retired "Standards Bureau" identity (Bureau Oxblood, Archivo Narrow) that `docs/ux-plan.md` §0 voids. It is not an input to this build and needs rewriting from the shipped result at finish.
- The `focused={false}` branches of EpicCard / FeatureCard / StoryCard / StoryList are reachable only from `FeatureTree.tsx`, which nothing but its own test renders. Dead presentation kept alive by tests; removing it is a structural call, not this pass's.
- `ux-plan.md` §3.6 (approval above evidence on `/review`) stays open — Phase 3, a different surface.
