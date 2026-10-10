# ADR 0114 — Curated capability concepts may select systems

## Status

Proposed 2026-10-10, for the owner to accept. Phase 0 of the ontology and impact plan
([plan](https://claude.ai/code/artifact/27b1b1d1-b01b-40d4-9264-1999bc29b2bf), from the
[catalogue ontology gap review](https://claude.ai/code/artifact/041e2507-4337-4cf9-80d5-ddd4b7f55470)).
Supersedes one rule each of ADR-0089 and ADR-0094, named below. Pairs with ADR-0115 (the product
verdict in analysis) and ADR-0116 (concepts reach generation). Built in knowledge-portal, which
keeps a copy.

## Context

Mapping selects a system in two ways today: the requirement names it (`named_systems`), or the
reasoner picks it from retrieved evidence. Business words that are not system names reach a
system only if the embedding happens to rank its record high.

Two earlier decisions kept every curated business structure out of selection:
- **ADR-0089** rejected "letting the fallback map systems": a capability domain's name in the text
  is not evidence that a particular system changes. Domain suggestions are advice only.
- **ADR-0094** made landscape domains "maintenance and browsing only": impacts, fingerprints and
  prompts ignore them.

Both were right for trees of area names. The plan adds something different: a business
capability concept (a SKOS-style concept with a preferred label, alternative labels, a
definition and a broader concept) that a system is linked to only when a maintainer accepts the
link. The Phase 0 golden set measures what this costs today. With the fake models, today's mapper
finds 8.6% of the systems a reviewer expects (knowledge-portal's `docs/slices/ontology-phase-0-baseline.md`), because
most requirements describe what the business needs, not which system does it.

## Decision

**A curated capability concept may select the systems linked to it.**
- The link is curated: a `KnowledgeCapability.concept_id` or an
  `OfferingComponent.capability_ids` entry, saved only through an accepted catalogue candidate
  or a maintainer's own edit, and published with the release (Phase 1).
- A requirement facet reaches a concept by label match or by the concept index (Phases 2 and 3),
  never by a domain or landscape name alone.
- A system selected this way carries its path (facet, then concept, then system) and the
  evidence behind each step, so a reviewer sees why it was chosen. The quote rules stay: an
  answer naming an id outside the release, or quoting text not in its evidence, is rejected.
- An uncovered concept is reported as a gap. It is never forced onto the nearest system.

**What stays as it was.**
- Capability domains (ADR-0089) and landscape domains (ADR-0094) never select a system. Their
  suggestions remain advice.
- Component names never select a system (ADR-0092). A component's linked concepts can, through
  the concept, once linked.
- Nothing AI-proposed is published without a maintainer accepting it (knowledge-portal's `AGENTS.md` §8). A
  suggested concept link is a candidate until then.

**The product verdict vocabulary** lives in knowledge-portal's domain
(`domain/architecture/verdicts.py`): change to an existing offering, new plan, new offering in
an existing family, new product line, or no verdict while questions are open.

**Every retrieval change is scored on the golden set** (knowledge-portal's `tests/fixtures/golden/`) before it
ships, with the fake models in CI and with the configured models by hand
(`python -m knowledge_portal.interfaces.evaluate`).

## Consequences

- Requirements that describe a need, not a system, can reach the right systems, with a path a
  reviewer can check.
- Maintainers curate one more structure, and concept links need review like any candidate. A
  release whose concepts are unlinked behaves as today.
- A wrongly accepted concept link now changes mapping, not just browsing. The golden set and the
  override rate (Phase 5) are how that is caught.
- Approval fingerprints here will include the concept path once impacts carry
  it, so a changed path re-opens review there (ADR-0115).

## Alternatives Considered

- **Keep concepts advisory, like domains.** Rejected: the golden set shows name matching misses
  most expected systems, and advice the reviewer must act on by hand does not raise recall.
- **Let capability domains select systems.** Rejected for the reason ADR-0089 gave: an area name
  is not evidence about a particular system.
- **An LLM-extracted knowledge graph.** Rejected in the gap review: links nobody reviewed would
  select systems.
