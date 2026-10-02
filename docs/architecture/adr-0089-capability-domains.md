# ADR 0089 — Capability domains

## Status

Accepted. Extends ADR-0016, ADR-0067 and ADR-0081. Builds on ADR-0087 and ADR-0088.

## Context

Capabilities were flat and belonged to one system each. The seed's 31 capabilities had no shared
business area: "Self-service ordering", "Mobile self-service", "SaaS ordering", "Assisted sales"
and "Back-office order capture" were five unrelated records. As a result:
- **Mapping had no fallback.** When no system matched an item, the reviewer saw an empty impact
  and nothing to go on.
- **Impact couldn't be read by business area**, only by system.
- **The catalogue couldn't be browsed by what the business does.**

A formal ontology (OWL/RDF) or an external taxonomy service would add tooling and operations
burden for a question a small, maintained tree answers.

## Decision

- **A shallow tree maintained with the release.**
  - `CapabilityDomain(id, name, name_ar, parent_id, description)` lives in
    `ArchitectureKnowledge.capability_domains`.
  - The release refuses duplicate ids, unknown parents, cycles, more than three levels, and two
    siblings with the same name.
  - `KnowledgeCapability.domain_id` is optional and must name a domain in the release. So a
    domain that still holds capabilities or other domains cannot be removed.
  - `domain_path()` gives a domain and its ancestors.
- **Seeded with eight business areas.** Order capture, Product catalogue, Customer management,
  Order orchestration and fulfilment, Resource and service, Assurance, Billing, and Enabling and
  integration. All 31 seed capabilities are placed, following eTOM-style groupings.
  - Existing databases keep their stored seed, because the seed is inserted only into an empty
    table.
  - A maintainer gets the domains by importing the updated seed file into a draft. There is no
    data migration, as the project is in development (the ADR-0080 precedent).
- **Files.**
  - YAML and JSON have an optional top-level `capability_domains` list, and a `domain` key per
    capability.
  - Excel has an optional Domains sheet and an optional `domain_id` column on Capabilities.
  - Older files import unchanged. A capability placed in an unlisted domain is refused, naming
    where it is.
  - Importing a file replaces the draft's domains along with its systems, and the import preview
    shows what that removes.
- **Diff and suggestions.**
  - The diff reports added, removed and changed domains (`name`, `name_ar`, `parent`,
    `description`), and a capability's `domain` change.
  - A capability suggestion that updates an existing capability keeps its domain. Extraction
    never proposes domains.
- **Evidence text.** A placed capability's line gains its path, for example
  `Assisted sales, quoting, and order capture (Order capture): …`, so retrieval can match domain
  words. An unplaced one is unchanged.
- **Impacts.**
  - `SystemCapability` gains `domain_id` and `domain_path`, taken from the pinned release at
    mapping time for mapped and connected systems.
  - When no catalogued system is mapped, `suggest_domains` scores each domain by whole-phrase hits
    in the item's text: its own names (Arabic included), plus the names and matching phrases of
    the capabilities placed in it and in the domains below it.
  - It returns at most two `DomainSuggestion`s, never a domain together with its own parent or
    child. Each carries the systems working in that domain and the words that matched.
  - Suggestions are advice. They add no system, and an impact refuses them alongside a
    catalogued system.
- **Show-only.**
  - Approval and review-evidence fingerprints ignore domain fields and suggestions. They are
    derived from the pinned release and the item text, which are already digested, so existing
    approvals stay valid.
  - Generation guidance strips them, so the `feature-v5` and `story-v5` prompts are unchanged.
  - Payloads write them only when present.
- **Export.**
  - The neutral contract moves to `1.3`: `ExportCapability.domain_path`.
  - The Systems sheet gains a `capability_domains` column.
- **UI.**
  - A "Domains" view in the catalogue workbench shows the tree, with counts, the systems behind
    each capability, the draft's changes, and the capabilities not placed yet.
  - The draft editor lists and edits domains. Remove explains what a domain still holds.
  - Each capability in the system dialog gets a domain picker.
  - The system dossier shows each capability's domain.
  - The impact panel shows each matched capability's domain and a "Matched business areas" line.
  - When nothing is mapped, the panel shows "Closest business areas" as a suggestion.

## Consequences

- Reviewers get a lead when mapping finds nothing, and they read impact by business area.
- Maintainers curate one more structure. Unplaced capabilities stay visible until they do.
- **Known limitation: coverage depends on the matching path.** On the packaged seed path, a
  mapped system carries only the capabilities whose phrases matched, so "Matched business areas"
  can leave out a mapped system's other areas. On the indexed path, a selected system carries all
  of its capabilities. Attaching only matched capabilities there, or all capabilities on the
  seed path, would change mapped content and approval fingerprints, so it is left as a
  follow-up.
- Word matching is lexical. Near-synonyms need adding as matching phrases, which the dossier
  already makes visible.

## Alternatives Considered

- **A formal ontology or an external taxonomy service.** Rejected: operational weight for no
  question the product asks.
- **Adopting TM Forum ODA components as the nodes.** Rejected for the seed: they fit the
  business-language capabilities poorly. Maintainers can rename or re-nest domains freely.
- **Tag fields on Epics and Features.** Rejected: domains follow from the architecture impact,
  which already belongs to Features and Stories. A second, hand-kept tag would drift.
- **Letting the fallback map systems.** Rejected: a domain name in the text is not evidence that
  a particular system changes. Suggestions stay advice.
