# ADR 0094 — Landscape domains and system descriptions

## Status

Accepted. Extends ADR-0089 and ADR-0081. Slice 2a of the structured-architecture-document plan.

## Context

A landscape document such as `SMB_Product_Architecture_Explorer_v4.md` places every system:
- **A Domains table** names eight TAM areas, such as Customer, Product, Service and Resource.
- **Each system row** says which area it sits in. Some rows add a sub-domain (Assisted,
  Un-assisted, Data & Case) and a Function: one sentence on what the system is for.

The catalogue had nowhere to keep any of this. A system had names, capabilities, components and
constraints, but no description and no place. The only domains were capability domains
(ADR-0089), and they answer a different question:
- **Capability domains** are business areas, such as Order capture or Billing, that group what
  systems *do*.
- **Landscape domains** say where a system *sits*. One system sits in one area, while its
  capabilities serve several business areas. CBCM holds customer data and is also the order
  store.

Folding the two into one tree would:
- mix those questions;
- skew the "Closest business areas" suggestions that score capability domains;
- force a single system into several business areas.

## Decision

**A second, separate tree on the release.**
- `LandscapeDomain(id, name, name_ar, parent_id, description)` lives in
  `ArchitectureKnowledge.landscape_domains`.
- It follows the capability-domain rules through one shared check, `_check_domains(..., noun)`:
  - unique ids;
  - known parents;
  - no cycles;
  - at most three levels;
  - sibling names unique.
- A sub-domain is a child, so Customer › Assisted is `customer-assisted` under `customer`.
- `ArchitectureKnowledge.landscape_path()` gives a domain and its ancestors.
- The same id may appear in both trees. They are different areas.

**Systems gain two optional fields.**
- `SystemDefinition.description`: what the system is for.
- `SystemDefinition.landscape_domain_id`: where it sits. It must name a landscape domain in the
  release, so a domain that still holds systems cannot be removed.

Both are optional and stored in the release's JSON, as with ADR-0089, so no migration is needed.

**Files.**
- **YAML/JSON:**
  - an optional top-level `landscape_domains` list;
  - per-system `description` and `landscape_domain` keys.
- **Excel:**
  - an optional `LandscapeDomains` sheet;
  - optional `description` and `landscape_domain_id` columns on Systems.
- **Older files** import unchanged.
- **Refusals:** a system placed in a domain the file does not list is refused, naming the system.
- **Import replaces** the draft's landscape domains along with its systems, and the preview shows
  it.

**The changes view.**
- The diff reports added, removed and changed landscape domains (`ChangedItem.LANDSCAPE_DOMAIN`),
  labelled by their path.
- A system's changed `description` and `landscape_domain` show as system field changes.

**Evidence text.**
- A system's index chunk gains its description and a `Landscape: Customer › Assisted` line, only
  when present. Systems without them keep their exact chunk text, so retrieval can match a
  system by what it is for and where it sits.
- Impacts, approval fingerprints, generation prompts and the backlog export are unchanged. This
  slice is maintenance and browsing only.

**API.**
- `SystemDefinitionSchema` gains `description` and `landscape_domain_id`, and the release response
  gains `landscape_domains`.
- `DraftUpdateRequest.landscape_domains` is optional. Leaving it out keeps the draft's tree, so
  clients that predate it lose nothing.

**UI (feature work, declared in the slice spec).**
- **The system drawer's Identity section** gains a Description field and a Landscape domain picker,
  with sub-domains indented.
- **"Edit manually"** lists the landscape tree above the capability tree in the same editor
  component, configured per tree. A sub-domain's id carries its parent's.
- **The Domains view** reads where the systems sit, then what they do. It lists the systems that
  are not placed yet.
- **The system dossier** shows the description and landscape path.

## Consequences

- A landscape's areas, sub-domains and system purposes can be kept, browsed and exported.
  Slice 2b will suggest them from documents.
- Two trees named "domains" need clear words. The UI always says "Landscape domains" or
  "Capability domains", never just "Domains", in editors and headings.
- Impact mapping does not yet use landscape domains. Using them is a later, separate decision.
- A system has exactly one landscape place. A system that truly spans areas is placed at their
  common parent, or left unplaced.

## Alternatives Considered

- **Reuse the capability-domain tree for systems.** It is cheaper, but it conflates "where it
  sits" with "what the business does", and changes `suggest_domains` scoring.
- **A free-text domain and sub-domain on each system.** It has no shared vocabulary, nothing to
  browse, and typos make new areas.
- **A system-to-domain link from the domain side.** That duplicates the ownership of placement.
  The capability precedent keeps placement on the placed item.

## Amendment — Suggested from documents (2026-10-01, slice 2b)

Landscape domains, placements and descriptions are now suggested from documents, and reviewed like
every other suggestion. This replaces ADR-0089's "Extraction never proposes domains" for landscape
domains only. Capability domains are still never proposed.

**Two new suggestion kinds, and a description on systems** (`domain/architecture/candidates.py`):
- **`landscape_domain`**
  - Carries an id (also its subject `system_id`), a name, an optional `parent_domain_id`, an Arabic
    name and a description.
  - **Matching:** it is the draft's domain with the same id, or with the same name under the same
    parent.
  - **Status:** a new domain is *New*; one whose parent is missing *Needs its domain first*; one
    that already exists only fills a missing description or Arabic name.
- **`placement`**
  - Carries a system and the landscape domain it sits in. The domain is found by id or, when only
    one has it, by name.
  - **Status:**
    - an unplaced system is *New*;
    - the same place is *Already in this version*;
    - a missing system or domain *Needs* it first;
    - moving a system that is already placed *Adds to an existing item* and is always decided one
      by one.
- **A system suggestion's `description`** fills a missing description and never replaces one.
- **Accept order:** landscape domains (parents first) → systems → placements → components →
  capabilities → constraints → dependencies.
  - Accept and Accept all save the release's landscape domains along with its systems and
    relationships.
- **Stored suggestions** read before these fields existed still load, because the fields are
  defaulted.

**The table reader proposes them exactly** (`catalogue-tables-v2`):
- **A Domains table** (a `Domain` column plus `ID` or `Code`) gives one domain per row. The ID is
  its key, and the code its description. These rows are not sent to the model.
- **A system row is placed:**
  - by its `Domain` cell, when it has one; a domain the Domains table did not list is still
    proposed;
  - otherwise by the heading of its table, matched to a domain by name or by the code in brackets
    ("Market & Sales (TAM · Market/Sales)").
- **Its `Sub-domain` cell** gives a sub-domain under that domain, keyed `customer-assisted` and
  proposed once, and the system is placed there.
- **Its `Function` cell** is the system's description.

**The model proposes them from prose, Word and PDF** (`catalogue-extraction-v8`):
- `ChangeOutput` gains the kinds `landscape_domain` and `placement`, and the fields `domain` and
  `parent_domain`.
- A system's `text` is its description.
- A sub-domain's key is its parent and name together, as the reader writes it, so both sources
  meet on one id.
- **Read rows:** the model proposes only capabilities and constraints from rows already read. Any
  system, dependency, domain or placement it proposes from them anyway is dropped.

**Review:**
- Domain suggestions read "A sub-domain of Customer".
- Placements read "Place BCRM in Customer › Assisted".
- Editing before accepting covers a domain's name, parent and description, a placement's system
  and domain, and a system's description.
- Grouped by system, landscape domains form a group of their own.
