# ADR 0096 — Journeys and their derived flow

## Status

Accepted. Extends ADR-0095. Slice 3c of the structured-architecture-document plan.

## Context

A product architecture document describes how an offering's order is fulfilled. Business Pro Plus
› New Activation, for example, is:
- **18 numbered activities.** Each has a phase, a track (MAIN, CORRECTION, SERVICE, FIELD and
  others), the system that performs it and the systems that support it, its system function and
  mode, whether the customer sees it, its components, its input and output, and its eTOM place.
- **7 flow rules:** a pass/fail decision, a correction loop, and four parallel tracks that rejoin.
- **18 activity integrations.** Each gives the interaction, interface, payload, timing and
  correlation key.
- **A mermaid diagram.** The document says it was itself reconstructed from the activities and
  rules.

The catalogue had nowhere for a journey. Yet it is the clearest account of which systems a change
to an order touches, and in what order.

## Decision

**Journeys live in the release** as `ArchitectureKnowledge.journeys`, in
`domain/architecture/journeys.py`. Each one is:
- **a `Journey`:** id, name, the `product_id` and `order_type_code` it fulfils, description,
  confidence, source;
- **its `Activity`s:** numbered, and sorted as numbers, so 75 comes before 100;
- **its `FlowRule`s:** a decision, a loop or a parallel track, with a condition, branch, group and
  the activity where it rejoins;
- **its `ActivityIntegration`s.**

The source's confidence is kept on every part, as for offerings.

**The flow is derived, never stored.** `journey_edges()` builds it from three things:
- each main-track activity to the next, unless a rule leaves that activity;
- every rule, labelled with its condition or branch;
- each parallel track back to the activity where it rejoins.

For the reported journey this gives exactly the document's 21 arrows. A person therefore edits
activities and rules, never arrows, and the drawing cannot drift from them. The API sends the
derived edges with each journey and ignores any edges sent back.

**Checks.**
- **A journey refuses:** duplicate activity numbers; rules or integrations naming activities it
  does not have; an order type without an offering.
- **The release refuses a journey naming:** a system, an offering, one of that offering's order
  types, or one of its components that the release does not have. So none of these can be
  removed while a journey names it, and the message says which journey and activity name it.

**Files.**
- **YAML/JSON** gain `journeys`:
  - activities name their `system`, `supporting` systems and `components`;
  - rules and integrations use `from` and `to`.
- **Excel** gains the sheets `Journeys`, `Activities`, `FlowRules` and `ActivityIntegrations`.
  Rows are gathered into the YAML shape. Each activity, rule and integration that is refused names
  its own row.

**The changes view** reports an added, removed or changed journey, and which of its parts
changed: activities, flow rules, integrations, or its own fields.

**Evidence.** Each journey is one evidence chunk, `journey <id>`. It walks the activities in order
with the system that performs each, its supporting systems and its system function, followed by
the integrations. A requirement about a step of an order thereby finds the systems around it.

**UI (declared feature work).**
- **A Journeys view.** Each journey shows:
  - its offering and order type;
  - an ordered activities table (activity, phase and track, performed by, supported by, mode), with
    systems that open their dossier;
  - **the drawn flow**;
  - its exceptions and side tracks in words;
  - an integrations table.
- **The drawn flow:**
  - **Layout:** one row per step, and parallel tracks side by side until they rejoin.
  - **Marks:** side tracks are dashed, loops arc up the left margin, and decisions are labelled.
  - **Accessibility:** it is one image with a summary, in a scrollable, focusable region, beside
    the table that says the same in words.
- **"Edit manually"** lists journeys, and adds, edits and removes them. Removing asks first.
  - **Activities** fold to one line: number, name and system.
  - **Rules and integrations** choose their activities from the journey's own.
  - **The order type** follows the chosen offering, and **components** come from it.
  - **Errors** appear beside their fields, and folded activities with errors open.
  - **Unsaved changes** are confirmed before closing.

## Consequences

- **Kept and drawn.** A journey's order and responsibilities can be maintained by hand or by file
  and drawn without a diagram tool. Slice 3d reads journeys from documents.
- **Shared with mapping.** Impact retrieval can find a journey's systems through its evidence.
  Showing the activities a mapped system performs is slice 3e.
- **The layout is deliberately simple.** It is rows by dependency, and is not a general graph
  layout. Very wide parallel sections scroll horizontally inside their region.
- **Some document fields are not modelled.** Phases and tracks are free text. A journey's flow
  sees only the rules and the main-track order, so a side-track activity that no rule reaches is
  drawn on its own.

## Alternatives Considered

- **Store the edges.** They would drift from the activities and rules, and a person would have to
  draw arrows by hand.
- **Store the mermaid text.** It is opaque to the catalogue: the systems behind each step could
  not be checked, retrieved or protected from removal.
- **A diagram library.** It adds a dependency for one view. The layout needed is a ranked list
  with side tracks, which a few lines of SVG draw within the design system's tokens.

## Amendment — Journeys suggested from documents (2026-10-01, slice 3d)

**One suggestion holds one whole journey.** `CandidateKind.JOURNEY` carries
`CandidateContent.journey`, with the journey's id as its subject. It is reviewed, edited and
accepted as a whole, like an offering, because its rules and integrations refer to its activities.
- **References are resolved when classified or accepted.** A journey names its systems, offering,
  order type and components as the reading found them.
  - Offerings, order types and components match by id, code or name, ignoring case and
    punctuation, so "NEW_ACTIVATION" is "New Activation".
  - A journey whose systems are missing *Needs its system first*.
  - A journey whose offering, or that offering's order type, is missing *Needs its product
    offering first* (`CandidateMatch.NEEDS_OFFERING`).
  - A journey whose components are missing *Needs its component first*.
  - Accepting refuses while any is missing, naming them.
- **Matching an existing journey.** A journey with the same id, or the same name for the same
  offering, is that journey. Accepting **replaces** it whole and keeps its id, and is always
  decided one by one.
- **Accept order.** Journeys are accepted last, after the offerings they fulfil.

**One journey, one suggestion.** `merge_journeys` combines readings of one journey:
- the first reading's facts win and later ones fill gaps;
- activities merge by number, rules by kind and activities, and integrations by their two
  activities;
- the offering and its order type travel together.

Before merging, each reading names its references by the ids they will have. Offerings suggested
in the same reading count, so the model's "Business Pro Plus" and the reader's `business-pro-plus`
are one offering.

**The table reader** (`catalogue-tables-v4`) reads a `Journey: X` section:
- **Activities table:** number, phase, track, performing and supporting systems, system function,
  mode, customer visible and evidence. Supporting systems split at `|`, `,` and `;`, and at `/`
  unless one system is named so.
- **Detail blocks.** Each `#### N. Title` gives its activity's description, and its `**Key:**
  value` bullets fill what the table left:
  - related components, as the offering's component ids;
  - input → output;
  - eTOM;
  - the evidence and its source.

  An activity only its details describe is kept.
- **Flow rules and integration details tables.**
- **The offering** is the product section the journey sits in, or the nearest one before it. Its
  order type is the one named like the journey.
- **A journey that does not hold together** is not suggested, and its rows go to the model as
  before. Examples: a rule naming an activity the journey does not have, or two activities with
  one number.
- **Rows sent to the model:**
  - flow-rule rows, detail bullets, step headings and the mermaid diagram are not sent;
  - activity rows and activity descriptions are sent marked read, so the model proposes only
    capabilities and constraints from them.

For the reported file: 18 activities, 7 rules and 18 integrations. 10 activities have components
as the offering's ids. The derived flow is the document's 21 arrows.

**The model** (`catalogue-extraction-v10`) proposes a `journey` from prose, Word or PDF. The answer
shape is lean:
- the offering and order type as written;
- each activity's number, name, track, performing and supporting systems and system function;
- only the rules that leave the main order.

Before use, the adapter makes it valid:
- each activity number is kept once;
- system names are stripped of decoration and resolved;
- a rule to an activity the journey lacks is left out.

**Prompt room.** A journey is the largest answer shape. With it, an 8,192-token local model would
have about 450 tokens of document per call, below the 800-token floor. So a reading whose context
leaves less than 1,600 tokens of room with journeys asks without them:
- `LEAN_SYSTEM_PROMPT` and `LeanExtractionOutput`;
- room stays at about 900 tokens;
- when the document mentions a journey, it warns that journeys in prose were not proposed and
  journey tables are still read.

Larger contexts and hosted models ask for journeys.

**Review.**
- A journey suggestion reads "Journey: New Activation — For Business Pro Plus › New Activation ·
  18 activities · 7 flow rules · 18 integrations".
- "Edit and accept" opens the journey drawer from slice 3c, offering the draft's offerings and
  those still suggested.
- A system or offering the version does not have yet stays chosen, marked "not in this version",
  so a correction never drops it.
- Grouped by system, journeys form a group of their own.
