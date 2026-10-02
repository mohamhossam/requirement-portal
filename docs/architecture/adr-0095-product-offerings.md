# ADR 0095 — Product offerings

## Status

Accepted. Extends ADR-0081 and ADR-0094. Slice 3a of the structured-architecture-document plan.

## Context

A product architecture document such as `SMB_Product_Architecture_Explorer_v4.md` describes a
commercial offering, Business Pro Plus. It gives:
- the offering's code, family, version, lifecycle, proposition and rules;
- its order types, one of them known but not offered;
- nine components: their type, whether each is mandatory and customer-visible, specs and details;
- twenty-two **component → system responsibilities**, each with a role such as
  `PRIMARY_ORCHESTRATOR` or `FIELD_FULFILLMENT`, the order types it applies to, and the
  document's own confidence (confirmed, inferred or a known gap);
- the offering's customer value and who it is for.

The catalogue had nowhere for any of this. It is the question impact mapping most needs answered:
"a change to Business Pro Plus' backup 5G touches which systems?"

The same words already mean other things here:
- the organisation catalogue's **products** (ADR-0080) group ownership under value streams;
- a system's **components** (ADR-0092) are its modules.

## Decision

**Offerings live in the release** as `ArchitectureKnowledge.products`. They are versioned,
reviewed, built and published with the systems they name.

- **The types live in `domain/architecture/products.py`:**
  - `ProductOffering` is made of `OrderType`s, `OfferingComponent`s, and `OfferingPoint`s (customer
    value and audiences).
  - Each component carries `ComponentResponsibility`s: a system, a role, what the system does, and
    the order types it applies to.
- **The names stay distinct.** The UI says "Product offerings". The code says `ProductOffering`
  and `OfferingComponent`, never `Product` or `Component`.
- **The source's confidence is kept as written.** Every fact may carry
  `SourceConfidence.CONFIRMED`, `INFERRED` or `GAP`, plus where it came from. This is the
  document's own claim, separate from a suggestion's stated or inferred basis.
- **A role is one code.** "Primary orchestrator" and `PRIMARY_ORCHESTRATOR` are the same, stored
  as the code and shown as words.
- **An offering refuses to contradict itself.** It refuses:
  - duplicate order-type codes or component ids;
  - a system with the same role twice in one component;
  - a responsibility naming an order type the offering does not have.
- **The release refuses responsibilities naming systems it does not have.** So a system an
  offering names cannot be removed, and the message says which offering and component name it.
- **Shared invariants** (`InvalidKnowledgeError` and the required-text check) move to
  `domain/architecture/invariants.py`, so offerings and the release share them without an import
  cycle. `knowledge.py` re-exports the error.

**Files.**
- **YAML/JSON** gain a nested `products` list. Responsibilities name their `system`. Unknown
  facts are left out.
- **Excel** gains five sheets:
  - `Products`;
  - `OrderTypes`;
  - `OfferingComponents`;
  - `Responsibilities`, with order types separated by `;`;
  - `ProductPoints` (`kind` is value or audience).

  Flags read yes or no. Rows are gathered into the YAML shape and read by the same code, so an
  error names its sheet and row.
- **Older files** import unchanged.
- **Import replaces** the draft's offerings with the file's, as it does systems.

**The changes view** reports an added, removed or changed offering (`ChangedItem.PRODUCT`).
- A changed offering names its fields.
- A component's own fields are reported separately from its "responsibilities".

**Evidence.** Each offering is one evidence chunk, `product <id>`. It holds:
- what the offering is and how it is ordered;
- each component;
- one line per responsibility, for example "Fibre Access — B2B Web (primary channel): Captures
  the order".

A requirement about a product therefore retrieves the systems behind it. System chunks are
unchanged, and an offering chunk is never mistaken for a system's own.

**API.**
- Releases carry `products`.
- `DraftUpdateRequest.products` is optional; leaving it out keeps the draft's offerings.

**UI (declared feature work).**
- **A Product offerings view.** Each offering shows:
  - its facts and confidence (as words, never colour alone);
  - its rules;
  - its order types, with "Not offered yet";
  - a components table;
  - a component × system table of roles, with row and column headers;
  - what each system does, with its order types;
  - its customer value and who it is for.

  A system opens its dossier.
- **"Edit manually"** lists offerings, and adds, edits and removes them. Removing asks first.
  - The offering drawer has five sections: the offering, order types, components with the systems
    that deliver each, customer value, and who it is for.
  - Errors appear beside their fields.
  - Facts the drawer does not show are kept.
  - Closing with unsaved changes asks first.

## Consequences

- **Faster inputs.** Products and their system responsibilities can be maintained by hand or by
  file now. Slice 3b suggests them from documents.
- **Better retrieval.** Impact retrieval can find a product's systems through its evidence chunk.
  Advisory product context on impacts is slice 3e.
- **Uncertainty stays visible.** A known gap or an inferred fact is visible wherever the offering
  is read.
- **Shared release.** Offerings sit in the release, so a busy offering makes the release larger.
  The schemas bound each list at the catalogue maximum.
- **No link to ownership.** Linking an offering to the organisation catalogue's product, for
  ownership, is deferred.

## Alternatives Considered

- **A separate products store.** References to versioned system ids would cross aggregates.
  Publish, diff, review and indexing would all need a second path.
- **Products as capabilities.** A capability belongs to one system. A component is delivered by
  several systems in different roles, and the role is the point.
- **Reuse the organisation catalogue's products.** Those group ownership and are maintained apart
  from the architecture release. Mixing the two would tie offerings to value streams and squads.

## Amendment — Offerings suggested from documents (2026-10-01, slice 3b)

**One suggestion holds one whole offering.** `CandidateKind.PRODUCT` carries
`CandidateContent.product`, with the offering's id as its subject. It is reviewed, edited and
accepted as a whole, because its rows refer to each other: responsibilities name components and
order types. Seventy row-level suggestions would be tedious and could disagree.
- **Systems are named as written and resolved when classified or accepted.** An offering whose
  systems are not all in the draft *Needs its system first*. Accepting it then refuses, naming
  them.
- **Matching an existing offering.** An offering with the same id, code or name as one in the
  draft is that offering:
  - when nothing differs, it is *Already in this version*;
  - otherwise accepting **replaces** it whole and keeps its id, and the suggestion is always
    decided one by one.
- **Accept order.** Offerings are accepted last, after the systems they name. Accepting saves the
  release's offerings.

**One offering, one suggestion.** A product section read in several calls, or by both the table
reader and the model, gives one offering in parts. `merge_offerings` combines them:
- the first reading's facts win and later ones fill gaps;
- order types merge by code, components by id, responsibilities by system and role, and points by
  name;
- every part's citations are kept.

**The table reader** (`catalogue-tables-v3`) reads a `Product: X` section:
- **The facts row:** code, family, version, lifecycle, evidence and source.
- **Prose:** paragraphs under a proposition heading become the proposition, and a "Product rules:"
  paragraph is split into rules.
- **Tables:**
  - Order types, with enabled as yes or no.
  - Customer value, and "Who is it for?" (fit or audience).
  - Components. A component marked GAP is **kept**, marked as a known gap.
  - Component → system responsibilities. Each responsibility's order types are matched to the
    offering's codes by name or code; others are left out.
- **Rows sent to the model:**
  - fact, order-type and point rows are not sent;
  - component and responsibility rows are sent marked read, so the model proposes only their
    capabilities.

**The model** (`catalogue-extraction-v9`) proposes a `product_offering` with a nested `offering`
from prose, Word or PDF. Before use, the adapter makes it valid:
- order types are keyed once, and components by code or name;
- each system is named once per role, without decoration;
- a responsibility keeps only the order types the offering has.

**Prompt room.** The nested offering made the answer schema three times larger. The answer
models now send a compact schema: no titles, descriptions or size limits, which validation still
enforces. The product rule is kept short. This holds an 8,192-token local model at about 900
tokens of document per call, above the 800-token floor, down from about 1,500 before this slice.

**Review.**
- An offering suggestion reads "Product offering: Business Pro Plus — 2 order types · 9 components
  · 22 system responsibilities".
- "Edit and accept" opens the offering drawer from slice 3a.
- Grouped by system, offerings form a group of their own.
