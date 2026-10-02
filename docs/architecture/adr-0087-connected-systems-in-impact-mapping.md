# ADR 0087 — Connected systems in architecture impact mapping

## Status

Accepted. Extends ADR-0016 and ADR-0067. Keeps ADR-0067's rejection of GraphRAG and a graph
database.

## Context

The published catalogue already records directed relationships between systems (for example
"DCRM → CBCM / CRMGW: DCRM captures back-office orders against the central customer domain").
Mapping used them only when both ends had been selected. `ResolveArchitectureKnowledge` and the
YAML adapter both kept a dependency only if the source and the target were in the impact.

So a Feature that touched DCRM showed DCRM alone. CBCM / CRMGW, the system the change is most
likely to break, never appeared. The reviewer had to know the catalogue to notice it.

A review of ontology, taxonomy and GraphRAG for this gap found no need for either a graph store
or LLM-built graph summaries:
- The graph is small and curated by maintainers. It is hundreds of records, not a corpus.
- GraphRAG community summaries cannot be traced back to an exact quote, which AGENTS.md §7 and
  §8 require.
- A walk of the relationships already in the release answers the question.

## Decision

- **One hop, both directions.** `domain/architecture/neighbours.adjacent()` returns the systems
  that share a published relationship with a mapped catalogued system but were not mapped
  themselves. It also returns the relationships that connect them.
  - Systems with more connections to the mapping come first, then by id.
  - At most 8 are kept. `omitted` counts the rest.
  - Declared systems that are not in the catalogue are not walked.
- **Connected, not mapped.** `ArchitectureImpact` and `ArchitectureKnowledgeMatch` gain
  `adjacent_systems`, `adjacent_dependencies` and `adjacent_omitted`, all defaulted.
  - The invariants keep them apart from `systems`: ids are disjoint, and each connecting
    dependency joins exactly one mapped system and one connected system.
  - The existing rule that `dependencies` connect mapped systems is unchanged. So `cross_system`,
    the review policy's cross-system risk and flags, and its dependency list behave exactly as
    before.
- **Resolved from the pinned release.** `ResolveArchitectureKnowledge.match` computes adjacency
  from the same published release it mapped against, on both the seed path and the indexed path.
  Connected systems carry their capabilities, constraints and organisation ownership, so the
  reviewer knows whom to ask.
- **Show-only.**
  - Approval and review-evidence fingerprints ignore connected systems. They are a pure function
    of the mapped systems and `knowledge_version`, which are already digested, so existing
    approvals stay valid.
  - Generation guidance strips them before the Feature and Story prompts see the match. The
    prompts stay byte-identical to their recorded versions.
- **Stored only when present.** The impact payload writes the new keys only when there are
  connected systems, and reads them as optional. Older impacts load unchanged.
- **Exported.**
  - The neutral contract moves to `1.1`, a compatible addition under ADR-0023.
    `ExportArchitecture` gains `adjacent_systems` and `adjacent_dependencies`.
  - The workbook adds a "Connected Systems" sheet, one row per connecting relationship. The
    "Systems" sheet still lists mapped systems only.
- **Shown.** The impact panel adds "Connected systems to check": each system with its squads and
  the relationship that connects it. The compact Story panel names them in one line.

## Consequences

- Reviewers see the systems next to the ones a Feature or Story changes, with the catalogued
  relationship as the evidence.
- The result is only as good as the catalogue's relationships. A missing relationship still
  hides a neighbour, as it did before.
- Hub systems can connect to many others. The cap keeps the panel readable, and the count keeps
  the cut visible.
- Adjacency is recomputed at mapping time. An impact mapped before this change shows no connected
  systems until its team refreshes the mapping. This follows ADR-0084: remapping is the team's
  choice.

## Alternatives Considered

- **GraphRAG or a graph database.** Rejected again for the reasons in ADR-0067, and because a
  one-hop walk over maintained relationships needs neither.
- **Multi-hop traversal.** Deferred. Two hops from a hub reach most of the catalogue, and an
  unranked list that long would not help a reviewer. Revisit with measured need.
- **Adding connected systems to `systems`.** Rejected. It would mark them as mapped, raise
  cross-system risk, change the review flags, and invalidate approvals for a list that is
  advisory.
- **Raising a review flag per connected system.** Rejected by the product owner for this slice
  (show-only).
