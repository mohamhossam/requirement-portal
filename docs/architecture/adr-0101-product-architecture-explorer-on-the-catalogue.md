# ADR 0101 — The product architecture explorer lives on the knowledge catalogue

## Status

Accepted 2026-10-05. Follows ADR-0098 and ADR-0099. For this platform, it replaces the original
repository's "ADR 0098 — Embedded product architecture explorer" on the
`smb-product-flow-architecture` branch. That number is taken here by ADR-0098 (three
repositories).

## Context

After the import, the original repository (`smb-ai-requirement-agent`) gained the **Product
Architecture Explorer** on its `smb-product-flow-architecture` branch, 14 commits after
`d5cfb57`. The explorer answers one question: for a product, an order journey and a channel,
which systems, handoffs and APIs take part, and on what evidence. It also generates a Solution
Architecture document (`.docx`) and drafts business change requests, including from Requirement
AI's approved-backlog export.

On that branch it is a single offline HTML file:
- Its facts sit in a hand-curated `model.json`: 2 products, 54 systems, 17 journeys and about
  1,180 facts, each with evidence.
- It is framed in a sandbox in the requirement UI, served without sign-in, and given its own nginx
  location and Content Security Policy.
- Changes to its facts reach the file only through an architect running `apply-change.mjs` and
  rebuilding.

That design does not fit this platform:
- **Ownership.** Architecture knowledge belongs to knowledge-portal (ADR-0098). The explorer's
  facts are the same kind of fact as the catalogue's offerings, journeys and systems, but kept in
  a second place with its own identifiers. That branch's own ADR named convergence with the
  catalogue as future work.
- **Content.** The product owner decided that the explorer's content must not be static. It is to
  be extracted from uploaded documents or entered by hand, and reviewed like any other catalogue
  content.

## Decision

**The explorer is a view of knowledge-portal's published catalogue.**
- It is a knowledge-portal screen that reads a published release: products, order types,
  components and their responsibilities, journeys, steps, flow rules and handoffs.
- It does not carry a model of its own. A concept the catalogue does not hold yet is shown as a
  gap, never filled in.
- The explorer's engine (scenario projection, impacted systems, integrations and the document
  generator) is ported into the knowledge-portal frontend and fed from the release.

**Content enters the way all catalogue content does.**
- Documents are uploaded and extracted into suggestions, which a person accepts. Alternatively,
  content is edited by hand or imported from a catalogue file into a draft.
- Every route then goes through Check and Publish, so nothing is published unreviewed.
- A business change request becomes a draft release with suggestions; `apply-change.mjs` has no
  equivalent here. A Requirement AI backlog export (schema 1.x) becomes one more source of
  suggestions.

**The explorer's model is imported once, then retired.**
- knowledge-portal's `scripts/convert_explorer_model.py` writes `model.json` as a catalogue file.
- An admin previews that file against a draft, imports it, reviews it and publishes it.
- Evidence keeps its confidence (confirmed, inferred or gap) and names its source.
- The script reports what the catalogue cannot hold yet, rather than forcing it into fields with
  another meaning: channels, plans and prices, tracking, NFRs, source levels and conflicts.

**The catalogue grows in vertical slices before the explorer reaches parity.** Each slice adds the
domain field, the extraction prompt and output, the table reader, the catalogue-file sheet, the
editor and the explorer view together:
1. a read-only explorer on what exists;
2. channels;
3. plans and prices;
4. realisation layers, tracking, NFRs and lifecycle;
5. source levels and conflicts;
6. the Solution Architecture document;
7. change requests from Requirement AI exports.

**What this repository keeps:**
- Requirement Engineering only. There is no explorer route, iframe, public route, `frame-src
  'self'` or explorer nginx location here.
- The backlog export stays the contract the explorer reads. Its schema stays 1.x unless both sides
  change together.
- At most, a link to the explorer in knowledge-portal.

**Access** is knowledge-portal's: `knowledge_admin` today. Opening read-only explorer access to
other signed-in users is a separate decision. Anonymous access, which the original branch had for
its MVP, is not carried over.

## Consequences

- **One home for architecture facts.** The impact mapper and the explorer read the same published
  release, so a correction made once reaches both.
- **The explorer is only as complete as the catalogue.** Until the later slices land, scenarios
  have no channel dimension, no prices and no tracking. They show those as gaps where the original
  file showed curated text. The parity check is the original engine's 39-scenario regression
  matrix, run against the seeded release.
- **No offline single file.** Architects lose the "open the HTML file anywhere" delivery. The
  Solution Architecture document is still downloadable.
- **Narrower audience for now.** Business users who opened the public MVP need an account and a
  role, until the access decision above is made.
- **Porting record.** Each repository's `UPSTREAM.md` records a decision for all 14 original
  commits.

## Alternatives Considered

- **Copy the static file and its iframe into requirement-portal.** Rejected: it keeps a second,
  hand-edited architecture model outside knowledge-portal, against ADR-0098, and against the
  product owner's decision that content is extracted or entered, not bundled.
- **Copy the static file into knowledge-portal unchanged.** Rejected for the same reason about
  content, and because its inline-script policy and sandbox would need a second CSP regime in
  knowledge-portal.
- **Keep `model.json` as a live import that is re-run on change.** Rejected: two editable sources
  would drift, and the catalogue's review and publish gate would be bypassed.
- **Put the engine or the document generator in platform-kernel.** Rejected: they carry business
  meaning (products, journeys, roles), which ADR-0100 keeps out of the kernel.
