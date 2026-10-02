# ADR 0097 — Product and journey context on impacts

## Status

Accepted. Extends ADR-0087, ADR-0089, ADR-0095 and ADR-0096. Slice 3e of the
structured-architecture-document plan.

## Context

Slices 3a–3d put product offerings and journeys in the catalogue. Impact mapping still used only
systems, capabilities and relationships.

Take an item that says "Business Pro Plus new activation: add the static IP option". It mapped to
systems, and a reviewer was not told two things the catalogue already knew:
- **who the offering makes responsible** for what the item names: the systems behind Static IP,
  and in which roles;
- **where each mapped system acts** in the offering's journey, and which systems hand over to it
  and from it.

Both are leads for a reviewer. Neither is evidence that a system is affected.

## Decision

**Two advisory notes on every impact**, read from the pinned release at mapping time:

- **`ProductContext`** — a product offering the item's text names, found by the offering's own
  name or code, or a component's name or code.
  - Words match as whole phrases, as capability domains do (ADR-0089). "BUSINESS_PRO_PLUS" reads
    as "Business Pro Plus", and matched words are reported as the catalogue writes them.
  - **Responsibilities** (`OfferingDuty`: component, system, role, description) are those of the
    components the item names, or every component's when it names none.
  - **Order type.** When the item names one of the offering's order types, a responsibility that
    lists its order types is kept only if it serves that one. An order type alone, such as "New
    Activation", names no offering.
  - At most two contexts. One that names the offering outranks one found only through a
    component.
- **`JourneyStep`** — a journey activity a mapped catalogued system performs or supports.
  - It carries the journey, the offering and order type the journey fulfils, and the activities
    the derived flow (ADR-0096) leads in from and out to, each with the system that performs it.
  - When the item names an offering, only that offering's journeys count, and only the named
    order type's journeys when one fulfils it. Otherwise every journey counts.
  - At most twelve steps, in journey order.

**Advice, never mapping.** These notes:
- **map no system.** An impact refuses a journey step of a system it did not map.
- **leave approval fingerprints unchanged.** The approval fingerprint lists the fields it reads,
  so existing approvals stay valid.
- **are stripped from generation guidance.** The feature and story prompts are unchanged.
- **are written to payloads only when present**, so older impacts keep their shape.

**API.** `ArchitectureImpactResponse.product_contexts` and `.journey_steps`.

**Export.** The neutral contract moves to `1.5`:
- `ExportArchitecture.product_contexts` and `.journey_steps`;
- JSON carries them as nested objects;
- Excel adds two sheets:
  - **Product Context:** one row per responsibility, or one row for an offering with none;
  - **Journey Steps:** one row per step, with the activities before and after as text.

**UI.** The impact panel adds two groups, apart from the mapped-system cards:
- **"Product offering named":**
  - the offering, and the order type when named;
  - the words in common;
  - each named component with its systems and roles.
- **"Journey steps to check":** grouped under each mapped system, each step with:
  - whether the system performs or supports it;
  - what the journey fulfils;
  - "After …" and "Then …" activities with their systems.

Compact mode keeps each note to one line.

## Consequences

- **More for the reviewer.** A reviewer sees the offering's own account of who does what, and the
  handovers either side of a change, without opening the catalogue.
- **Re-mapping is needed for existing impacts.** Existing impacts gain the notes only when mapped
  again. Nothing is migrated.
- **Matching is literal.** An item that describes an offering without naming it, or names it
  differently from the catalogue, gets no product context. A catalogue alias for offerings is
  left for later.
- **Caps are silent.** Steps beyond twelve are not counted or announced. In practice a few mapped
  systems acting in one offering's journey stay well under it.

## Alternatives Considered

- **Map the offering's responsible systems as impact.** That would let catalogue wording
  outweigh the mapping's evidence, and approvals would move with every catalogue edit.
- **Put journey steps on each `SystemReference`.** Systems are part of the approval fingerprint
  and the generation guidance, so each would need the advice stripped again. The impact-level
  list is kept apart once.
- **Show the whole journey.** A reviewer needs the step and its neighbours. The Journeys view in
  the catalogue has the rest.
